from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .serializers import MessageSerializer, RegisterSerializer, CustomUserSerializer, ContactListSerializer, ContactSerializer, ElementSerializer, PackageSerializer, SurveySerializer, QRSerializer
from .models import Message, ContactList, Contact, Element, PackagePlan, CustomUser, EmailConfirmationToken, SurveyResponse, AnalyticsData, QRCode, ShopifyStore
from rest_framework import generics
from sms.models import Sms, CampaignStats
from io import BytesIO
from django.shortcuts import redirect
from django.http import HttpResponse
from .utils.googleAnalytics import sample_run_report
from .email.email import send_confirmation_email, send_welcome_email, send_confirmation_email_account_close
from django.db.models import Sum
from django.db import transaction
from sms.models import Sms
from datetime import datetime
from django.http import JsonResponse
import os
import requests
from reportlab.lib import colors
import requests
from reportlab.platypus import Table, TableStyle
from django.core.cache import cache
from django.conf import settings
from django.utils.timezone import now
from djoser.views import UserViewSet
from reportlab.pdfgen import canvas
from .permissions import HasPackageLimit
import stripe
from .auth import get_shop_info
from .queries import GET_CUSTOMERS_QUERY, GET_TOTAL_CUSTOMERS_NR, CREATE_CUSTOMER_QUERY, DELETE_CUSTOMER_QUERY, UPDATE_CUSTOMER_QUERY
from .shopify_functions import ShopifyFactoryFunction
from base.utils.calculations import calculate_avg_performance, format_number, clicks_rate, calculate_deliveribility


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims
        token['username'] = user.username
        token['first_name'] = user.first_name
        token['last_name'] = user.last_name

        try:
            custom_user = CustomUser.objects.get(username=user.username)
            print('CUSS', custom_user)
            shopify_obj = ShopifyStore.objects.filter(
                email=custom_user.email).first()
            serialized_data = custom_user.serialize_package_plan()
            token['shopify_token'] = shopify_obj.access_token if shopify_obj else None
            token['sms_count'] = custom_user.sms_count
            token['user_type'] = custom_user.user_type
            token['archived_state'] = custom_user.archived_state
            token['package_plan'] = serialized_data
            token['custom_email'] = custom_user.custom_email
        except CustomUser.DoesNotExist:
            token['package_plan'] = None

        return token


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

    def validate(self, **kwargs):
        pass


class ShopifyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        # Get the Authorization header
        authorization_header = request.headers.get('Authorization')
        if not authorization_header or not authorization_header.startswith('Shopify '):
            return None  # No Shopify token, skip this authentication class

        # Extract the Shopify token
        shopify_token = authorization_header.split(' ')[1]

        # Validate the Shopify token (optional: verify with Shopify's API)
        if not shopify_token:
            raise AuthenticationFailed('Invalid Shopify token')

        # Retrieve the user associated with the Shopify token
        try:
            user = CustomUser.objects.get(
                shopify_token=shopify_token)  # Replace with your logic
        except CustomUser.DoesNotExist:
            raise AuthenticationFailed(
                'No user associated with this Shopify token')

        return (user, shopify_token)


class CustomUserViewSet(UserViewSet):
    def set_password(self, request, *args, **kwargs):
        response = super().set_password(request, *args, **kwargs)
        if response.status_code == status.HTTP_204_NO_CONTENT:
            user = CustomUser.objects.get(id=request.user.id)
            user.last_password_change = now()
            user.save(update_fields=['last_password_change'])
        return response


class OAuthAuthorization(APIView):
    def get(self, request):
        shop = request.GET.get("shop")
        if not shop:
            return JsonResponse({"error": "Missing shop parameter"}, status=400)

        auth_url = (
            f"https://{shop}/admin/oauth/authorize?"
            f"client_id={settings.SHOPIFY_API_KEY}"
            f"&scope={settings.SHOPIFY_SCOPES}"
            f"&redirect_uri={settings.SHOPIFY_REDIRECT_URI}"
        )
        return redirect(auth_url)


class ShopifyAuth(APIView):
    def get(self, request):
        shop = request.GET.get("shop")
        if not shop:
            return JsonResponse({"error": "Missing shop parameter"}, status=400)
        print(shop)
        user_token = ShopifyStore.objects.get(
            shop_domain=shop
        )
        custom_user_obj = user_token.user
        custom_user = CustomUser.objects.get(id=custom_user_obj.id)
        user_serializer = CustomUserSerializer(custom_user)

        return JsonResponse({"user": user_serializer.data, "token": user_token.access_token, "shopifyDomain": user_token.shop_domain}, status=200)


class CallbackAuthView(APIView):
    def get(self, request):
        shop = request.GET.get("shop")
        code = request.GET.get("code")

        if not shop or not code:
            return JsonResponse({"error": "Missing shop or code parameter"}, status=400)

        token_url = f"https://{shop}/admin/oauth/access_token"
        payload = {
            "client_id": settings.SHOPIFY_API_KEY,
            "client_secret": settings.SHOPIFY_API_SECRET,
            "code": code,
        }

        response = requests.post(token_url, json=payload)
        data = response.json()

        if "access_token" in data:
            # Save the access token to the database (for future API requests)
            access_token = data["access_token"]
            # Store it in the session for authenticated API calls
            request.session["shopify_access_token"] = access_token

            shop_data = get_shop_info(shop, access_token)

            shopify_store = ShopifyStore.objects.filter(
                shop_domain=shop).first()
            # url = f"https://{shopify_domain}/admin/api/2025-01/graphql.json"
            # shopify_factory = ShopifyFactoryFunction(
            #     GET_TOTAL_CUSTOMERS_NR, shop, access_token, url, request)
            # customers = shopify_factory.get_total_customers()

            if not shopify_store:
                # Create the ShopifyStore and associate it with the user
                shopify_store = ShopifyStore.objects.create(
                    email=shop_data.get('email'),
                    shop_domain=shop,
                    access_token=access_token,
                )
            else:
                # Update the access token if the store already exists
                shopify_store.access_token = access_token
                shopify_store.save()

            return redirect(f"https://spplane.app/?shop={shop}")
        else:
            return JsonResponse({"error": "OAuth failed", "details": data}, status=400)


class SendEmailConfirmationTokenAPIView(APIView):

    def post(self, request, format=None):

        user = request.data['user']['id']

        user_instance = CustomUser.objects.get(id=user)
        token = EmailConfirmationToken.objects.create(user=user_instance)
        send_confirmation_email(
            email=user_instance.email, token_id=token.pk, user_id=user_instance.pk)
        return Response(data=None, status=201)


@api_view(['GET'])
def confirmation_token_view(request, token_id, user_id):
    try:
        with transaction.atomic():
            token = EmailConfirmationToken.objects.get(pk=token_id)
            user = token.user
            user.is_active = True
            user.save()

            if user.is_active is True:
                if user.stripe_custom_id is None:
                    stripe_customer = stripe.Customer.create(
                        name=f'{user.first_name} {user.last_name}',
                        email=user.email,
                    )
                    user.stripe_custom_id = stripe_customer['id']
                    user.save()
                if user.welcome_mail_sent is False:
                    send_welcome_email(user.email, user)
                    user.welcome_mail_sent = True
                    user.save()
            return Response(status=status.HTTP_200_OK)
    except EmailConfirmationToken.DoesNotExist:

        return Response(status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user(request, id):
    user = CustomUser.objects.get(id=id)
    serializer = CustomUserSerializer(user)

    return Response(serializer.data)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_user(request, id):
    try:

        user = CustomUser.objects.get(id=id)
        serializer = CustomUserSerializer(
            user, data=request.data, partial=True)
        if serializer.is_valid(raise_exception=True):
            serializer.update(user, validated_data=request.data)
            if request.data['is_active'] == False:
                send_email = send_confirmation_email_account_close(user.email)
                if send_email:
                    return Response({"message": "Email dispatched"}, status=status.HTTP_200_OK)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(f'There has been some error: {e}')


@api_view(['GET'])
def note_view(request, id):
    try:

        message = Message.objects.get(id=id)
        elements = Element.objects.filter(message=message).order_by('order')
        serializer = ElementSerializer(elements, many=True)
        message_serializer = MessageSerializer(message)
        response_data = {
            'elements': serializer.data,
            'message': message_serializer.data,
            # You can customize this message
        }

    except Exception as e:
        return Response(f'There has been some error: {e}')
    return Response(response_data)


@api_view(['PUT'])
def update_element(request, id):
    try:
        element = Element.objects.get(id=id)
        element.order = request.data['order']
        element.save()
        serializer = ElementSerializer(element)
        return Response(serializer.data)
    except Element.DoesNotExist:
        raise Response("Element not found")


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_notes(request):
    try:
        user = request.user
        print(user)
        archive = request.GET.get('archive', None)
        sort_by = request.GET.get('sort_by', None)
        # search_query = request.GET.get('search', '')

        customUser = CustomUser.objects.get(user_ptr_id=user.id)

        # if search_query:
        #     notes = user.message_set.filter(
        #         message_name__icontains=search_query)

        if customUser.archived_state == True:
            customUser.archived_state = False
            customUser.save()
        # Determine which messages to fetch based on 'archive' parameter
        if archive == 'true':
            # Fetch only archived messages
            notes = user.message_set.filter(status='archived')
        else:
            # Fetch only non-archived messages
            notes = user.message_set.exclude(status='archived')

        # Apply sorting if provided
        if sort_by:
            notes = notes.order_by(sort_by)

        # Serialize the notes
        serializer = MessageSerializer(notes, many=True)
        serialized_data = serializer.data

        # Count the 'sent' messages for additional information
        sent_message_count = notes.filter(status='sent').count()

        return Response({"messages": serialized_data, "messages_count": sent_message_count})

    except Exception as e:
        return Response({"error": f"There has been some error: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@permission_classes([IsAuthenticated])
@api_view(['GET'])
def get_arvhived(request):
    try:
        user = request.user
        sort_by = request.GET.get('sort_by', None)
        search_query = request.GET.get('search', '')

        customUser = CustomUser.objects.get(user_ptr_id=user.id)

        notes = user.message_set.filter(status='archived')

        if search_query:
            notes = user.message_set.filter(
                message_name__icontains=search_query)

        if customUser.archived_state == True:
            customUser.archived_state = False
            customUser.save()

        # Apply sorting if provided
        if sort_by:
            notes = notes.order_by(sort_by)

        # Serialize the notes
        serializer = MessageSerializer(notes, many=True)
        serialized_data = serializer.data

        # Count the 'sent' messages for additional information
        sent_message_count = notes.filter(status='sent').count()

        return Response({"messages": serialized_data, "messages_count": sent_message_count})

    except Exception as e:
        return Response({"error": f"There has been some error: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
# Contact lists


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_packages(request):
    user = request.user
    cache_key = f"plans_for_user:{user.id}"
    # Try to fetch data from cache
    cached_data = cache.get(cache_key)

    if cached_data is None:

        package = PackagePlan.objects.all()
        serializer = PackageSerializer(package, many=True)
        data = serializer.data
        cache.set(cache_key, {"plans": data,
                              }, timeout=settings.CACHE_TTL)
        return Response(data)
    else:
        data = cached_data['plans']
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_contact_lists(request):

    user = CustomUser.objects.get(id=request.user.id)
    user_package = user.package_plan
    contact_list = user.contactlist_set.all()
    serializer = ContactListSerializer(contact_list, many=True)
    shopify_domain = request.headers.get('shopify-domain', None)
    package_limits = {
        'Gold package': {'contact_lists': 20, 'recipients': 10000},
        'Silver package': {'contact_lists': 8, 'recipients': 5000},
        'Basic package': {'contact_lists': 5, 'recipients': 6},
        'Trial Plan': {'contact_lists': 1, 'recipients': 5}
    }
    if user_package.plan_type in package_limits:
        limits = package_limits[user_package.plan_type]
    else:
        limits = package_limits['Trial Plan']

    if shopify_domain:
        url = f"https://{shopify_domain}/admin/api/2025-01/graphql.json"
        shopify_token = request.headers['Authorization'].split(' ')[1]
        shopify_factory = ShopifyFactoryFunction(
            GET_TOTAL_CUSTOMERS_NR, shopify_domain, shopify_token, url, request=request)
        recipients_count = shopify_factory.get_total_customers()
        max_recipients_allowed = limits['recipients']
        capped_recipients_count = min(recipients_count, max_recipients_allowed)
        return Response({"data": serializer.data, "limits": limits, "recipients": capped_recipients_count})
    else:

        recipients = Contact.objects.filter(users=user)

        recipients_count = recipients.count()

        # Get the limits based on the user's package plan

        return Response({"data": serializer.data, "limits": limits, "recipients": recipients_count})


@api_view(['GET,PUT'])
@permission_classes([IsAuthenticated])
def get_contact_list(request, pk):
    try:
        contact_list = ContactList.objects.get(id=pk)

        serializer = ContactListSerializer(contact_list)
    except Exception as e:
        return Response(f'There has been some error: {e}')

    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_contacts(request, id):
    try:
        shopify_domain = request.headers.get('shopify-domain', None)
        if shopify_domain:
            shopify_domain = request.headers['shopify-domain']
            url = f"https://{shopify_domain}/admin/api/2025-01/graphql.json"
            shopify_token = request.headers['Authorization'].split(' ')[1]
            shopify_factory = ShopifyFactoryFunction(
                GET_CUSTOMERS_QUERY, shopify_domain, shopify_token, url, request=request)

            response = shopify_factory.get_customers()

            if response.status_code == 200:
                data = response.json()

                customers = data.get("data", {}).get("customers", {})

                return Response(customers, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"error": "Failed to fetch customers from Shopify",
                     "details": response.json()},
                    status=response.status_code,
                )
        else:
            contact_list = ContactList.objects.get(id=id)
            cache_key = f"user_contacts:{contact_list.id}"

            # Check for sorting query parameters
            contacts = Contact.objects.filter(contact_list=contact_list)

            # Apply search filtering if the search parameter is provided
            search_query = request.GET.get('search', '')
            if search_query:
                contacts = contacts.filter(first_name__icontains=search_query)

            # Apply sorting if the sort_by parameter is provided
            sort_by = request.GET.get('sort_by', None)
            if sort_by and sort_by in ['first_name', '-first_name', 'created_at', '-created_at']:
                contacts = contacts.order_by(sort_by)

            serializer = ContactSerializer(contacts, many=True)
            cache.set(cache_key, {"contacts": serializer.data},
                      timeout=settings.CACHE_TTL)

            return Response({"customers": serializer.data, "contact_list_recipients_nr": contact_list.contact_lenght})

    except Exception as e:
        return Response(f'There has been some error: {e}')


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def contact_detail(request, id=None):
    try:
        shopify_domain = request.headers.get('shopify-domain', None)

        if shopify_domain:
            shopify_token = request.headers['Authorization'].split(' ')[1]
            url = f"https://{shopify_domain}/admin/api/2025-01/graphql.json"

            shopify_factory = ShopifyFactoryFunction(
                UPDATE_CUSTOMER_QUERY, shopify_domain, shopify_token, url, request=request)

            response = shopify_factory.update_customer()

            return Response({"response": response})
        else:
            contact = Contact.objects.get(id=id)

        if request.method == 'GET':
            serializer = ContactSerializer(contact)
            return Response(serializer.data, status=status.HTTP_200_OK)

        elif request.method == 'PUT' and not shopify_domain:

            serializer = ContactSerializer(
                contact, data=request.data, partial=True)
            if serializer.is_valid():
                cache_key = f"user_contacts:{request.user.id}"
                cache.delete(cache_key)
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Contact.DoesNotExist:
        return Response({"error": "Contact not found"}, status=status.HTTP_404_NOT_FOUND)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_message(request, id):
    try:
        message = Message.objects.get(id=id)

        serializer = MessageSerializer(
            message, data=request.data, partial=True)
        if serializer.is_valid(raise_exception=True):
            serializer.update(message, validated_data=request.data)
            if 'archived' in request.data['status']:

                Sms.objects.filter(message=message.id).delete()
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(f'There has been some error: {e}')


@api_view(['POST'])
@permission_classes([IsAuthenticated, HasPackageLimit])
def create_contact(request, id):
    try:
        shopify_domain = request.headers.get('shopify-domain', None)
        if shopify_domain:

            url = f"https://{shopify_domain}/admin/api/2025-01/graphql.json"
            shopify_token = request.headers['Authorization'].split(' ')[1]

            shopify_factory = ShopifyFactoryFunction(
                CREATE_CUSTOMER_QUERY, shopify_domain, shopify_token, url, request=request)

            response = shopify_factory.create_customers()

            if response.status_code == 200:
                data = response.json()
                if data.get("data", {}).get("customerCreate", {}).get("userErrors"):
                    return Response(
                        {"error": "Failed to create customer",
                            "details": data["data"]["customerCreate"]["userErrors"]},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                customer = data.get("data", {}).get(
                    "customerCreate", {}).get("customer", {})
                return Response(customer, status=status.HTTP_201_CREATED)
            else:

                return Response(
                    {"error": "Failed to create customer",
                        "details": data['details']},
                    status=response.status_code,
                )

        else:
            custom_user = CustomUser.objects.get(id=request.user.id)

            contact_list = ContactList.objects.get(id=id)

            serializer = ContactSerializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                serializer.save(contact_list=contact_list, users=custom_user)
                if not request.data['firstName'] and request.data['phone']:
                    return Response({'detail': 'Empty form submission.'}, status=status.HTTP_400_BAD_REQUEST)

                serializer.save(contact_list=contact_list, users=request.user)

                cache_key = f"user_contacts:{contact_list.id}"
                cache.delete(cache_key)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def create_contact_via_qr(request, id):
    try:
        contact_list = ContactList.objects.get(unique_id=id)
        users = contact_list.users
        analytic = AnalyticsData.objects.get(custom_user=users)
        print(request.data)
        serializer = ContactSerializer(
            data=request.data)
        if serializer.is_valid(raise_exception=True):
            if not request.data.get('first_name') or not request.data.get('phone_number'):
                return Response({'error': 'Empty form submission.'}, status=status.HTTP_400_BAD_REQUEST)
            with transaction.atomic():
                analytic.tota_subscribed += 1
                analytic.save()
            # Save the contact, linking it to the existing contact_list
            # Only pass contact_list, no need for users here.
            serializer.save(contact_list=contact_list, users=users)

            return Response(serializer.data, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response(f'There has been some error: {e}', status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_qr_code(request, id):
    try:
        print('YOO')
        contact_list = ContactList.objects.get(id=id)
        print(contact_list)
        qr_code_data = QRCode.objects.get(contact_list=contact_list.id)
        serializer = QRSerializer(qr_code_data)
        print(qr_code_data, "QRR")
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        print(e)
        return Response(f'There has been some error: {e}', status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_package_limits(request):
    # Assuming the user's package plan is stored in the user object or user profile
    user = request.user  # Assuming user is authenticated

    # Define package limits
    package_limits = {
        'Gold': {'contact_lists': 20, 'recipients': 10000},
        'Silver': {'contact_lists': 8, 'recipients': 5000},
        'Basic': {'contact_lists': 5, 'recipients': 1000},
        'Trial': {'contact_lists': 1, 'recipients': 5}
    }

    # Get the user's package plan
    # Replace 'package_plan' with the actual attribute name
    user_package = user.package_plan

    # Get the limits based on the user's package plan
    if user_package in package_limits:
        limits = package_limits[user_package]
    else:
        # Default to Trial package if user's package is not recognized
        limits = package_limits['Trial']

    return Response(limits)


@api_view(['GET'])
def handle_unsubscribe(request, id):
    try:
        with transaction.atomic():
            contact = Contact.objects.get(id=id)
            contact.delete()
            analytics = AnalyticsData.objects.get(custom_user=contact.users)
            analytics.tota_unsubscribed += 1
            analytics.save()
        return Response('Contact deleted successfully', status=status.HTTP_200_OK)
    except Exception as e:
        return Response(f'There has been an error: {e}', status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def purchase_package(request, id):
    try:
        user = CustomUser.objects.get(id=id)
        package_plan = PackagePlan.objects.get(id=request.data['package_plan'])

        user.package_plan = package_plan
        user.sms_count += package_plan.sms_count_pack
        user.save()

        serializer = CustomUserSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(f'There has been some error: {e}')


class RegisterAPI(generics.GenericAPIView):
    serializer_class = RegisterSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            user = serializer.save()
            return Response({
                "user": CustomUserSerializer(user, context=self.get_serializer_context()).data
            }, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CreateNote(generics.GenericAPIView):
    serializer_class = MessageSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):

            message = serializer.save()
            cache_key = f"messages:{request.user.id}"
            cache.delete(cache_key)
            return Response({
                "note": MessageSerializer(message, context=self.get_serializer_context()).data
            })
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_list(request, id):

    try:
        user = CustomUser.objects.get(id=id)
        serializer = ContactListSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            serializer.save(users=user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(f"Field cannot be blank:{e}", status=status.HTTP_400_BAD_REQUEST)


class CreateElement(generics.GenericAPIView):
    serializer_class = ElementSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            element = serializer.save()
            if element.element_type == 'Text' and not element.text:
                # Check if the element type is 'Text' and the value is empty
                return Response({'error': 'Text element must not have a non-empty value'}, status=status.HTTP_400_BAD_REQUEST)
            elif element.element_type == 'Button' and not element.button_title:
                return Response({'error': 'Button element must not have a non-empty value'}, status=status.HTTP_400_BAD_REQUEST)
            elif element.element_type == 'Survey':
                if not element.survey:
                    return Response({'error': 'Button element must not have a non-empty value'}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    element.save_response()
            return Response({
                "element": ElementSerializer(element, context=self.get_serializer_context()).data
            })
        else:
            return Response('There has been an error', status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_message(request, id):

    try:
        message = Message.objects.get(id=id)
        message.delete()
        cache_key = f"messages:{request.user.id}"
        cache.delete(cache_key)
        return Response("Message deleted!")
    except Exception as e:
        return Response(f'There has been an error:{e}')


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_element(request, id):
    try:
        element = Element.objects.get(id=id)
        element.delete()
        return Response("Element deleted!")
    except Exception as e:
        return Response(f'There has been an error:{e}')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def delete_contact_recipient(request, id):
    try:
        shopify_domain = request.headers.get('shopify-domain', None)
        if shopify_domain:
            shopify_token = request.headers['Authorization'].split(' ')[1]
            # Shopify GraphQL endpoint
            url = f"https://{shopify_domain}/admin/api/2025-01/graphql.json"

            shopify_factory = ShopifyFactoryFunction(
                DELETE_CUSTOMER_QUERY, shopify_domain, shopify_token, url, request=request)
            response = shopify_factory.delete_customer()

            if response.get("data", {}).get("customerDelete", {}).get("userErrors"):
                print('ALAA')
                return Response(
                    {"error":  response["data"]["customerDelete"]["userErrors"],
                     },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            deleted_customer_id = response.get("data", {}).get(
                "customerDelete", {}).get("deletedCustomerId")
            return Response({"deleted_customer_id": deleted_customer_id}, status=status.HTTP_200_OK)
        else:
            contact = Contact.objects.get(id=id)
            contact.delete()
            cache_key = f"user_contacts:{request.user.id}"
            cache.delete(cache_key)
            return Response("Recipient deleted!")
    except Exception as e:
        return Response(f'There has been an error:{e}')


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_contact_list(request, id):
    try:
        contact_list = ContactList.objects.get(id=id)
        Contact.objects.filter(contact_list=contact_list).delete()
        contact_list.delete()
        return Response("List deleted successfully!")
    except ContactList.DoesNotExist:
        return Response("List not found", status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_analytics_data(request, record_id):
    sms = Sms.objects.get(message=record_id)

    start_date = sms.created_at
    end_date = datetime.now().date()
    analytics_data, periodic_data = sample_run_report(
        record_id=record_id, start_date=start_date, end_date=end_date, recipients=sms.sms_sends)
    avg_data_calc = calculate_avg_performance(periodic_data)

    return Response({'message': 'Data returned!', 'data': analytics_data, 'period_data': periodic_data, "avg_data": avg_data_calc})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_results(request, id):
    response = {}
    element = Element.objects.filter(message=id, element_type='Survey')
    if element:
        survey = SurveyResponse.objects.get(element=element[0].id)
        serializer = SurveySerializer(survey)
        response = serializer.data
    # If you want to access the related SurveyResponse for each Element
    else:
        response = False
    return Response({'survey_responses': response})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_total_analytic_values(request, id):
    custom_user_id = CustomUser.objects.get(user_ptr_id=id)
    analytics_data = AnalyticsData.objects.get(custom_user=custom_user_id)
    overall_calculated_data = analytics_data.calculate_performance()
    formatted_total_spend = format_number(analytics_data.total_spend)
    formatted_clicks_rate = clicks_rate(
        analytics_data.total_clicks, analytics_data.total_sends)
    formated_deliveribility = calculate_deliveribility(
        analytics_data.total_delivered, analytics_data.total_sends)

    return Response({

        'overall_rate': overall_calculated_data,
        'total_views': analytics_data.total_views,
        'total_sends': analytics_data.total_sends,
        'total_clicks': analytics_data.total_clicks,
        'clicks_rate': formatted_clicks_rate,
        'total_spend': formatted_total_spend,
        'deliveribility': formated_deliveribility,
        'total_subscribed': analytics_data.tota_subscribed,
        'total_unsubscribed': analytics_data.tota_unsubscribed,
        'archived_state': custom_user_id.archived_state
    })


@api_view(['PUT'])
# @permission_classes([IsAuthenticated])
def handle_survey_response(request, id):
    # Get the element and survey response instance
    element = Element.objects.get(id=id)
    survey_response = SurveyResponse.objects.get(element=element)
    survey_type = request.data.get('survey_type')
    # Assuming the frontend sends the response type ('like' or 'dislike') in the request data
    response_type = request.data.get('response_type')

    # Update the corresponding field based on the response type
    if survey_type == 'Like/Dislike':
        if response_type == 'like':
            survey_response.like_response = (
                survey_response.like_response or 0) + 1
        elif response_type == 'dislike':
            survey_response.dislike_response = (
                survey_response.dislike_response or 0) + 1

    elif survey_type == 'Q Survey':
        survey_response.numeric_response = (
            survey_response.numeric_response or 0) + 1

    # Save the changes
    survey_response.save()

    return Response({'message': 'Survey response updated successfully'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_analytics(request, id):

    try:

        campaign_stats = CampaignStats.objects.get(id=id)
        fileName = f'Analyticss report for {campaign_stats.name}.pdf'
        doc_title = f'Analytics for {campaign_stats.name}'
        title = f'Results of your {campaign_stats.name} campaign'
        table_data = [
            ['Start Date', 'End Date', 'Views', 'Clicks', 'Unsubscribed',
             'Performance', 'Audience'],  # Headers
            [campaign_stats.campaign_start, campaign_stats.campaign_end, campaign_stats.engagement, campaign_stats.total_clicks,
             campaign_stats.unsub_users, campaign_stats.overall_perfromance, campaign_stats.audience]
        ]
        textLines = [
            'Below you can find table with detailed information about progress of this campaign.', 'If you have any questions please dont hesitate to contact us beniagic@gmail.com']
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer)
        pdf.setTitle(doc_title)

        # Change to desired font family and size
        pdf.setFont("Helvetica-Bold", 20)
        pdf.drawCentredString(250, 770, title)

        pdf.setFont("Helvetica", 12)
        y = 700
        x = 50
        for line in textLines:
            pdf.drawString(x, y, line)  # Position each line appropriately
            y -= 20

        table = Table(table_data)

        # Add styling to the table
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),  # Header row background
            # Header row text color
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            # Align all columns to center
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  # Header font bold
            ('FONTSIZE', (0, 0), (-1, 0), 12),  # Header font size
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),  # Header padding
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),  # Row background
            ('GRID', (0, 0), (-1, -1), 1, colors.black),  # Grid lines for table
        ]))

        # Draw the table at a specific position on the canvas
        table.wrapOn(pdf, 400, 500)  # Define available width and height
        table.drawOn(pdf, 50, 600)  # Position the table on the PDF page

        explanation_start_y = 550  # Starting Y position for explanations
        explanations = [
            ("Start Date", "Campaign start date, the campaign by default runs for 5 days, then it gets" +
             "automatically archived and stats are being calculated."),
            ("End Date", "Campaign end date. As stated above, the date which campaign ends unless user manually stops it before the 5th day."),
            ("Views", "Total amount of views accumulated during the days of campaign run. So the amount of people who viewed your content."),
            ("Clicks", "Total amount of clicks, this takes into account button clicks, link clicks, and SMS clicks of the campaign itself."),
            ("Unsubscribed", "The amount of users who unsubscribed from your contact list."),
            ("Performance", "The overall performance of this campaign. It's measured by engagement" +
             "success versus how many people the message was sent to minus unsubscribed users."),
            ("Audience", "Total amount of people to whom the message was sent, including SMS messages that didn't reach recipients.")
        ]

        def draw_wrapped_text(pdf, x, y, text, max_width):
            words = text.split(' ')
            line = ''
            for word in words:
                if pdf.stringWidth(line + word + ' ', "Helvetica", 10) < max_width:
                    line += word + ' '
                else:
                    pdf.drawString(x, y, line)
                    y -= 15  # Adjust Y position for next line
                    line = word + ' '  # Start a new line with the current word
            if line:  # Draw the last line
                pdf.drawString(x, y, line)
                y -= 15
            return y

        for header, explanation in explanations:
            pdf.setFont("Helvetica-Bold", 10)  # Set font to bold for header
            pdf.drawString(50, explanation_start_y, f'{header} - ')
            # Measure width of the header text
            text_width = pdf.stringWidth(f'{header} - ', "Helvetica-Bold", 10)

            # Set font back to normal for the explanation text
            pdf.setFont("Helvetica", 10)
            # Call the draw_wrapped_text function to handle wrapping
            explanation_start_y = draw_wrapped_text(
                pdf, 50 + text_width, explanation_start_y, explanation, 400)  # Max width 500
            explanation_start_y -= 10  # Max width 500

        # Update with the correct path to your logo
        logo_path = os.path.join(os.getcwd(), 'base/spp.logo.png')

        if not os.path.exists(logo_path):
            raise FileNotFoundError(f"Logo file not found at: {logo_path}")
        # Adjust position and size as needed

        # Add thank you message
        pdf.setFont("Helvetica-Bold", 12)
        # Adjust Y position for the thank you message
        thank_you_y = 150  # Y position for the thank you text
        pdf.drawCentredString(
            150, thank_you_y, "Thank you for using Sendperplane")

        logo_y = thank_you_y - 60  # Adjust for spacing
        pdf.drawImage(logo_path, 50, logo_y, width=150, height=50)
        pdf.setFont("Helvetica", 8)  # Set a smaller font size
        pdf.drawString(30, 30, "All rights reserved ©Sendperplane 2024")
        pdf.save()

        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{fileName}"'

        return response

    except Exception as e:
        return Response(f'There has been an error: {e}')


@api_view(['GET'])
def export_analytics_csv(request, id):
    pass


@api_view(['GET'])
def check_limit(request, id):
    try:
        contact_list = ContactList.objects.get(unique_id=id)
        users = contact_list.users
        analytic = AnalyticsData.objects.get(custom_user=users)
        can_sign_up = False
        if analytic.contacts_limit_reached is True:
            can_sign_up = False
            return Response({"can_sign_up": f"{can_sign_up}"})
        else:
            can_sign_up = True
            return Response({"can_sign_up": f"{can_sign_up}"})
    except Exception as e:
        return Response({"message": f"{e}"})
