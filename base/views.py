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
from .email.email import send_confirmation_email, send_welcome_email, send_confirmation_email_account_close, send_email_notification
from django.db.models import Sum
from django.db import transaction
from sms.models import Sms
from datetime import datetime
from django.http import JsonResponse
from . import serializers
import os
import requests
import hmac
import hashlib
import base64
import json
import uuid
import logging
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from reportlab.lib import colors
import requests
from reportlab.platypus import Table, TableStyle
from django.core.cache import cache
from django.conf import settings
from django.utils.timezone import now
from djoser.views import UserViewSet
from reportlab.pdfgen import canvas
from .utils import helpers
from .permissions import HasPackageLimit
import stripe
from .auth import get_shop_info
from .queries import (
    GET_CUSTOMERS_QUERY,
    GET_TOTAL_CUSTOMERS_NR,
    GET_CUSTOMERS_ORDERS,
    GET_PRODUCT,
    CREATE_CUSTOMER_QUERY,
    GET_ALL_PRODUCTS,
    DELETE_CUSTOMER_QUERY,
    UPDATE_CUSTOMER_QUERY,
    GET_SHOP_ORDERS,
    GET_SHOP_INFO
)
from .shopify_functions import ShopifyFactoryFunction
from base.utils.calculations import calculate_avg_performance, format_number, clicks_rate, calculate_deliveribility


utils = helpers.Utils()
logger = logging.getLogger(__name__)

environment = settings.ENVIRONMENT


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims
        token['username'] = user.username
        token['first_name'] = user.first_name
        token['last_name'] = user.last_name
        try:
            logger.info("----Authentication started----")
            custom_user = CustomUser.objects.get(custom_email=user.email)
            shop_id = None
            shopify_obj = ShopifyStore.objects.filter(
                email=custom_user.email).first()
            logger.info("----ShopifyObject----")
            logger.info(shopify_obj)
            if shopify_obj:
                url = f"https://{shopify_obj.shop_domain}/admin/api/2025-01/graphql.json"
                shopify_factory = ShopifyFactoryFunction(
                    shopify_obj.shop_domain, shopify_obj.access_token, url, request=None, query=GET_SHOP_INFO)
                response = shopify_factory.get_shop_info()
                if response.status_code == 200:
                    data = response.json()
                    shop_id = data.get('data', {}).get('shop', {})['id']
            serialized_data = custom_user.serialize_package_plan()

            token['shopify_token'] = shopify_obj.access_token if shopify_obj else None
            token['shopify_id'] = shop_id if shopify_obj else None
            token['shopify_domain'] = shopify_obj.shop_domain if shopify_obj else None
            token['shopify_connect'] = custom_user.shopify_connect if custom_user else None
            token['sms_count'] = custom_user.sms_count
            token['user_type'] = custom_user.user_type
            token['archived_state'] = custom_user.archived_state
            token['package_plan'] = serialized_data
            token['custom_email'] = custom_user.custom_email
            return token
        except CustomUser.DoesNotExist:
            raise AuthenticationFailed(
                'No user associated with this Shopify token')
        except Exception as e:
            return Response({"error": "Something wen't wrong, contact support"}, status=status.HTTP_404_NOT_FOUND)


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
                    first_name=shop_data.get('shopOwnerName')
                )
            else:
                # Update the access token if the store already exists
                shopify_store.access_token = access_token
                shopify_store.save()

            return redirect(f"https://spplane.app/register?shop={shop}")
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
        # archived, draft, scheduled, sent, active

        sort_by = request.GET.get('sort_by', '-created_at')  # Default sort

        customUser = CustomUser.objects.get(user_ptr_id=user.id)
        if customUser.archived_state:
            customUser.archived_state = False
            customUser.save()

        # Default to all messages if no type is provided
        notes = user.message_set.filter(status='Draft')

        # Apply sorting
        try:
            notes = notes.order_by(sort_by)
        except Exception as e:
            notes = notes.order_by('-created_at')

        # Count sent messages (optional, based on returned queryset)

        serializer = MessageSerializer(notes, many=True)
        return Response({
            "messages": serializer.data,

        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": f"There has been some error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_scheduled_campaigns(request):
    try:
        user = request.user

        notes = user.message_set.filter(status='Scheduled')
        # Serialize the notes
        serializer = MessageSerializer(notes, many=True)
        serialized_data = serializer.data

        # Count the 'sent' messages for additional information

        return Response({"messages": serialized_data}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": f"There has been some error: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_active_campaigns(request):
    try:
        user = request.user
        customUser = CustomUser.objects.get(user_ptr_id=user.id)
        campaigns = user.message_set.filter(status='sent')
        serializer = MessageSerializer(campaigns, many=True)
        serialized_data = serializer.data
        return Response({"messages": serialized_data}, status=status.HTTP_200_OK)
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


class ContactListsView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        try:
            user = CustomUser.objects.get(id=request.user.id)
            user_package = user.package_plan
            contact_list = user.contactlist_set.all()
            serializer = ContactListSerializer(contact_list, many=True)
            shopify_domain = request.headers.get('shopify-domain', None)
            limits = utils.get_package_limits(user_package)

            return Response({"data": serializer.data, "limits": limits}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):
        try:
            user = CustomUser.objects.get(id=request.data['user_id'])

            request_data = request.data

            serializer = ContactListSerializer(data=request_data)
            if serializer.is_valid(raise_exception=True):
                serializer.save(users=user)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(f"Field cannot be blank:{e}", status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        try:
            shopify_domain = request.headers.get('shopify-domain', None)
            user_id = request.data['user_id']
            user = CustomUser.objects.get(id=user_id)
            contact_list = ContactList.objects.get(
                id=request.data['list_id'])
            was_shopify_list = False
            if transaction.atomic():
                if shopify_domain and contact_list.shopify_list:
                    user.shopify_connect = False
                    user.save()
                    was_shopify_list = True

                Contact.objects.filter(contact_list=contact_list).delete()
                contact_list.delete()
                return Response({"message": "List deleted successfully!", "data": was_shopify_list}, status=status.HTTP_200_OK)
        except ContactList.DoesNotExist as e:
            return Response(f"error:{e}", status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(f"error:{e}", status=status.HTTP_400_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_contacts(request, id):
    try:
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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_product(request):
    try:
        shopify_domain = request.headers.get('shopify-domain', None)
        if shopify_domain:
            url = f"https://{shopify_domain}/admin/api/2025-01/graphql.json"
            shopify_token = request.headers['Authorization'].split(' ')[1]
            shopify_factory = ShopifyFactoryFunction(
                shopify_domain, shopify_token, url, request=request, query=GET_PRODUCT)

            product = shopify_factory.get_products_insights()
            orders = shopify_factory.get_shop_orders()
            if product.status_code == 200 and orders.status_code == 200:

                product_data = product.json()
                product = product_data.get("data", {}).get("product", {})
                orders_data = orders.json()
                data_map = utils.map_single_product_with_orders(
                    product, orders_data)

                cache_key = f"shopify_product_id:{shopify_domain}:{product['id']}"
                cache.set(cache_key, {"shopify_product": data_map},
                          timeout=settings.SMART_INSIGHTS_CACHE)

                return Response(data_map, status=status.HTTP_200_OK)
        else:
            return Response(
                {"error": "Failed to fetch customers from Shopify",
                 "details": response.json()},
                status=response.status_code,
            )

    except Exception as e:
        return Response(f'There has been some error: {e}')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_insights(request):
    try:
        logger.info('---Getting insights---')
        shopify_domain = request.headers.get('shopify-domain', None)
        if shopify_domain:
            cache_key = f"shopify_product_id:{shopify_domain}:{request.data['product_id']}"
            product_data = cache.get(cache_key)
            logger.info('---cached insights---')
            insights = utils.get_insights(product_data)
            logger.info(insights)
            return Response({"data": insights}, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response(f'There has been some error: {e}')


@api_view(['GET'])
def get_shop_shopify(request):
    try:
        shop = request.GET.get("shop")  # Get the 'shop' param from the URL
        if not shop:
            return Response({"error": "Missing shop parameter"}, status=status.HTTP_400_BAD_REQUEST)
        shopify_factory = ShopifyStore.objects.get(shop_domain=shop)
        serializer = serializers.ShopifyShopSerializer(shopify_factory)
        print(serializer.data)
        return Response({"shop": serializer.data}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": f'There has been some error: {e}'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def contact_detail(request, id=None):
    try:

        shopify_domain = request.headers.get('shopify-domain', None)
        contact_list = ContactList.objects.get(id=id)
        print(contact_list.shopify_list)
        if shopify_domain and request.method == 'PUT' and contact_list.shopify_list:
            print('DDDDDDDDDD')
            shopify_token = request.headers['Authorization'].split(' ')[1]
            url = f"https://{shopify_domain}/admin/api/2025-01/graphql.json"

            shopify_factory = ShopifyFactoryFunction(
                shopify_domain, shopify_token, url, request=request, query=UPDATE_CUSTOMER_QUERY)

            response = shopify_factory.update_customer()
            shopify_customer_id = (
                response.get('data', {})
                .get('customerUpdate', {})
                .get('customer', {})
                .get('id')
            )
            contact = Contact.objects.get(custom_id=shopify_customer_id)
            serializer = ContactSerializer(
                contact, data=request.data, partial=True)
            if serializer.is_valid():
                cache_key = f"user_contacts:{request.user.id}"
                cache.delete(cache_key)
                serializer.save()

            return Response({"response": response}, status=status.HTTP_200_OK)

        # if request.method == 'GET':
        #     serializer = ContactSerializer(contact)
        #     return Response(serializer.data, status=status.HTTP_200_OK)

        elif request.method == 'PUT':

            contact = Contact.objects.get(custom_id=request.data['id'])
            serializer = ContactSerializer(
                contact, data=request.data, partial=True)
            if serializer.is_valid():
                cache_key = f"user_contacts:{request.user.id}"
                cache.delete(cache_key)
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "Method not allowed"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    except Exception as e:
        print(e)
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
@permission_classes([IsAuthenticated])
def create_contact(request, id):
    try:
        shopify_domain = request.headers.get('shopify-domain', None)

        contact_list = ContactList.objects.get(id=id)

        if shopify_domain and contact_list.shopify_list:

            url = f"https://{shopify_domain}/admin/api/2025-01/graphql.json"
            shopify_token = request.headers['Authorization'].split(' ')[1]

            shopify_factory = ShopifyFactoryFunction(
                shopify_domain, shopify_token, url, request=request, query=CREATE_CUSTOMER_QUERY)
            print(request.data)
            response = shopify_factory.create_customers()

            if response.status_code == 200:
                data = response.json()
                if data.get("data", {}).get("customerCreate", {}).get("userErrors"):
                    return Response(
                        {"error": "Failed to create customer",
                            "details": data["data"]["customerCreate"]["userErrors"]},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                custom_user = CustomUser.objects.get(id=request.user.id)
                random_custom_id = str(uuid.uuid4())

                contact_list = ContactList.objects.get(id=id)
                data = request.data.copy()
                data['custom_id'] = random_custom_id

                required_fields = ['firstName', 'lastName', 'phone', 'email']
                missing_fields = [
                    f for f in required_fields if not data.get(f)]
                if missing_fields:
                    return Response(
                        {"detail": "Missing required fields",
                            "missing": missing_fields},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                serializer = ContactSerializer(data=data)
                serializer.is_valid(raise_exception=True)
                serializer.save(contact_list=contact_list, users=custom_user)

                cache_key = f"user_contacts:{contact_list.id}"
                cache.delete(cache_key)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:

                return Response(
                    {"error": "Failed to create customer",
                        "details": data['details']},
                    status=response.status_code,
                )

        else:
            custom_user = CustomUser.objects.get(id=request.user.id)
            random_custom_id = str(uuid.uuid4())

            contact_list = ContactList.objects.get(id=id)
            data = request.data.copy()
            data['custom_id'] = random_custom_id

            required_fields = ['firstName', 'lastName', 'phone', 'email']
            missing_fields = [f for f in required_fields if not data.get(f)]
            if missing_fields:
                return Response(
                    {"detail": "Missing required fields",
                        "missing": missing_fields},
                    status=status.HTTP_400_BAD_REQUEST
                )

            serializer = ContactSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save(contact_list=contact_list, users=custom_user)

            cache_key = f"user_contacts:{contact_list.id}"
            cache.delete(cache_key)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_bulk_contacts(request):
    try:
        shopify_domain = request.headers.get('shopify-domain', None)

        bulk_data = request.data.get('data', None).get('bulk_data')
        print('0', bulk_data)
        if not bulk_data:
            return Response({"detail": "No data provided."}, status=status.HTTP_400_BAD_REQUEST)
        required_fields = ['firstName', 'lastName', 'phone', 'email']
        invalid_items = []
        contacts_to_create = []
        print('1')
        custom_user = CustomUser.objects.get(id=request.user.id)
        contact_list_id = request.data.get("data", None).get('list_id', None)
        print('2')
        try:
            contact_list = ContactList.objects.get(id=contact_list_id)
        except ContactList.DoesNotExist:
            return Response({"error": "Contact list not found"}, status=status.HTTP_404_NOT_FOUND)
        print('3')
        if shopify_domain:
            url = f"https://{shopify_domain}/admin/api/2025-01/graphql.json"
            shopify_token = request.headers['Authorization'].split(' ')[1]

            shopify_factory = ShopifyFactoryFunction(
                shopify_domain, shopify_token, url, request=request, query=CREATE_CUSTOMER_QUERY)
        for idx, profile in enumerate(bulk_data):
            # profile = utils.convert_keys(profile)
            print('converterd', profile)
            missing_fields = [f for f in required_fields if not profile.get(f)]
            if missing_fields:
                print('missing?')
                invalid_items.append({"index": idx, "missing": missing_fields})
                continue
            serializer = ContactSerializer(data=profile)
            print('here')
            if serializer.is_valid():
                contact = Contact(
                    first_name=serializer.validated_data['first_name'],
                    last_name=serializer.validated_data['last_name'],
                    phone_number=serializer.validated_data['phone_number'],
                    email=serializer.validated_data['email'],
                    contact_list=contact_list,
                    users=custom_user
                )
                contacts_to_create.append(contact)
            else:
                invalid_items.append(
                    {"index": idx, "errors": serializer.errors})
        if shopify_domain:
            print('enter shopify')
            response = shopify_factory.create_customers_bulk()
            if response:
                return Response({"error": response.get('error')}, status=status.HTTP_400_BAD_REQUEST)
        if contacts_to_create:
            Contact.objects.bulk_create(contacts_to_create)
            contact_list.update_contact_count(contact_list)

        cache_key = f"user_contacts:{contact_list.id}"
        cache.delete(cache_key)

        return Response({
            "created": len(contacts_to_create),
            "invalid": invalid_items,
            "data": ContactSerializer(contacts_to_create, many=True).data
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_create_contacts(request):

    try:
        shopify_domain = request.headers.get('shopify-domain', None)
        if shopify_domain:
            contacts_response = []
            url = f"https://{shopify_domain}/admin/api/2025-01/graphql.json"
            shopify_token = request.headers['Authorization'].split(' ')[1]

            shopify_factory = ShopifyFactoryFunction(
                shopify_domain, shopify_token, url, request=request, query=GET_CUSTOMERS_QUERY)

            customers = shopify_factory.get_customers()
            # if response.status_code == 200:
            # data = response.json()
            print(customers)
            # customers = data.get("data", {}).get(
            #         "customers", {}).get("edges", [])
            # print(data)
            with transaction.atomic():
                custom_user = CustomUser.objects.get(id=request.user.id)
                custom_user.shopify_connect = True
                custom_user.save()
                contact_list = ContactList.objects.get(
                    id=request.data['list_id'])
                contact_list.shopify_list = True
                contact_list.save()

                for customer in customers:
                    node = customer.get('node', {})

                    if not node.get("phone") or not node.get("firstName"):
                        continue
                    contact_data = {
                        "custom_id": node.get("id"),
                        "firstName": node.get("firstName"),
                        "lastName": node.get("lastName"),
                        "email": node.get("email"),
                        "phone": node.get("phone"),
                        # YYYY-MM-DD
                        "created_at": node.get("createdAt", None)[:10] if node.get("createdAt") else None,
                    }
                    serializer = ContactSerializer(
                        data=contact_data)

                    if serializer.is_valid(raise_exception=True):

                        serializer.save(contact_list=contact_list,
                                        users=custom_user)
                        contacts_response.append(serializer.data)

        return Response({"data": contacts_response}, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def create_contact_via_qr(request, id):
    try:
        contact_list = ContactList.objects.get(unique_id=id)
        users = contact_list.users

        analytic = AnalyticsData.objects.get(custom_user=users)
        if contact_list.shopify_list:
            shopify_obj = utils.get_shopify_token(users)

            url = f"https://{shopify_obj.shop_domain}/admin/api/2025-01/graphql.json"
            shopify_factory = ShopifyFactoryFunction(
                shopify_obj.shop_domain, shopify_obj.access_token, url, request=request, query=CREATE_CUSTOMER_QUERY)

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
                with transaction.atomic():
                    analytic.tota_subscribed += 1
                    analytic.save()
                return Response(customer, status=status.HTTP_201_CREATED)
            else:

                return Response(
                    {"error": "Failed to create customer",
                        "details": data['details']},
                    status=response.status_code,
                )

        else:
            serializer = ContactSerializer(
                data=request.data)
            if serializer.is_valid(raise_exception=True):
                if not request.data.get('firstName') or not request.data.get('phone'):
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

        contact_list = ContactList.objects.get(id=id)

        qr_code_data = QRCode.objects.get(contact_list=contact_list.id)
        serializer = QRSerializer(qr_code_data)

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


class CreateElement(generics.GenericAPIView):
    serializer_class = ElementSerializer

    def post(self, request):
       # serializer = self.get_serializer(data=request.data)
        data = request.data
        files = request.FILES
        carousel_images = []
        idx = 0
        while True:
            img = {}
            url_key = f'carousel_images[{idx}][external_url]'
            file_key = f'carousel_images[{idx}][image]'
            # Add external_url if present
            if url_key in data:
                img['external_url'] = data[url_key]
                img['image_src'] = data[url_key]
            # Add image file if present
            if file_key in files:

                img['image'] = files[file_key]
                if environment == 'development':
                    img['image_src'] = f'http://localhost:8000/media/{files[file_key]}'
                elif environment == 'production':
                    img['image_src'] = f'{settings.MEDIA_URL}{files[file_key]}'
            if not img:
                break
            carousel_images.append(img)
            idx += 1
        plain_data = {k: v[0] if isinstance(
            v, list) else v for k, v in data.lists()}
        plain_data['carousel_images'] = carousel_images

        serializer = self.get_serializer(data=plain_data)
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
def delete_contact_recipient(request, id=None):
    try:
        contact = Contact.objects.get(id=id)
        contact.delete()
        cache_key = f"user_contacts:{request.user.id}"
        cache.delete(cache_key)
        return Response("Recipient deleted!")
    except Exception as e:
        return Response(f'There has been an error:{e}')


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
        'total_delivered': analytics_data.total_delivered,
        'total_undelivered': analytics_data.total_not_delivered,
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_shopify_products_orders(request):
    try:
        shopify_domain = request.headers.get('shopify-domain', None)
        search_query = request.GET.get('search', None)
        if shopify_domain:
            shopify_token = request.headers['Authorization'].split(' ')[1]
            # Shopify GraphQL endpoint
            url = f"https://{shopify_domain}/admin/api/2025-01/graphql.json"

            shopify_factory = ShopifyFactoryFunction(
                shopify_domain, shopify_token, url, request=request, query=None)
            products_response = shopify_factory.get_products(
                {"first": 10, "query": search_query})
            orders_response = shopify_factory.get_shop_orders({"first": 10})
            logger.info('---Shopify Products Response---')

            product_data = products_response.json()

            orders_data = orders_response.json()
            if products_response.status_code == 200 and orders_response.status_code == 200:

                data_map = utils.map_products_n_orders(
                    product_data, orders_data)
                logger.info('---Shopify Products Dictionary---')
                logger.info(data_map)
                return Response(data_map, status=status.HTTP_200_OK)
            else:

                return Response(
                    {"error": "Failed to fetch products",
                     "details": product_data},
                    status=products_response.status_code,
                )
        else:
            logger.info('---Shopify Products Dictionary---')
            return Response({"error": "No shopify domain"}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:

        logger.info('---Shopify Products Dictionary---')
        return Response(
            {"error": f"{e}"},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_shop_orders(request):
    shopify_domain = request.headers.get('shopify-domain', None)
    if shopify_domain:
        shopify_token = request.headers['Authorization'].split(' ')[1]
        # Shopify GraphQL endpoint
        url = f"https://{shopify_domain}/admin/api/2025-01/graphql.json"
        shopify_factory = ShopifyFactoryFunction(
            GET_SHOP_ORDERS, shopify_domain, shopify_token, url, request=request)
        response = shopify_factory.get_shop_orders()

        if response.status_code == 200:

            data = response.json()
            if data.get("errors", {}):
                return Response(
                    {"error": "Failed to fetch products",
                        "details": data["errors"]["message"]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            orders = data.get("data", {}).get(
                "orders", {}).get("edges", {})
            print("BLIMEE", orders)
            return Response(orders, status=status.HTTP_200_OK)
        else:

            return Response(
                {"error": "Failed to fetch products",
                    "details": data['details']},
                status=response.status_code,
            )


@require_http_methods(['POST'])
@csrf_exempt
def customer_data_request_webhook(request):

    shopify_hmac = request.META.get('HTTP_X_SHOPIFY_HMAC_SHA256')
    if shopify_hmac:

        body = request.body
        hashit = hmac.new(settings.SHOPIFY_API_SECRET.encode(
            'utf-8'), body, hashlib.sha256)
        calculated_hmac = base64.b64encode(hashit.digest()).decode()

        if not hmac.compare_digest(calculated_hmac, shopify_hmac):
            return HttpResponse(status=401)  # Unauthorized

        data = json.loads(body)

        print('Webhook triggered! We are not storing customers data with this webhook.')

        return HttpResponse(status=200)
    return Response({"error": "Missing shopify signature!"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@require_http_methods(['POST'])
@csrf_exempt
def customer_redact_request_webhook(request):

    shopify_hmac = request.META.get('HTTP_X_SHOPIFY_HMAC_SHA256')
    if not shopify_hmac:
        logger.warning("Missing HMAC header in customer redact webhook.")
        return HttpResponse("Missing signature", status=400)

    try:
        body = request.body
        expected_hmac = base64.b64encode(
            hmac.new(settings.SHOPIFY_API_SECRET.encode(),
                     body, hashlib.sha256).digest()
        ).decode()
        if not hmac.compare_digest(expected_hmac, shopify_hmac):
            logger.warning("Invalid HMAC signature.")
            return HttpResponse("Unauthorized", status=401)

        data = json.loads(body)
        logger.info(f"Customer redact webhook payload: {data}")
        shop_domain = data.get('shop_domain')
        customer_email = data.get('customer', {}).get('email')
        if not shop_domain:
            logger.error("Shop domain missing in payload.")
            return HttpResponse("Bad request", status=400)
        try:
            with transaction.atomic():
                shop = ShopifyStore.objects.get(shop_domain=shop_domain)
                user = CustomUser.objects.filter(
                    custom_email=shop.email).first()
                if user:
                    contact_list = ContactList.objects.filter(
                        users=user, shopify_list=True).first()
                Contact.objects.get(email=customer_email).delete()

                logger.info(
                    f"Customer with id {customer_email} redacted for shop: {shop_domain}")

                if contact_list and len(contact_list) == 0:
                    user.shopify_connect = False
                    user.save()
                logger.info(f"Customers deleted for shop: {shop_domain}")

                return HttpResponse(status=200)

        except ShopifyStore.DoesNotExist:
            logger.warning(f"ShopifyStore not found for domain: {shop_domain}")
            return HttpResponse(status=404)

    except Exception as e:
        logger.exception("Unhandled error in customer redact webhook.")
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def webhook_debug_view(request):
    print("🔔 Shopify webhook reached Django view")
    print("Headers:", dict(request.headers))
    print("Body:", request.body)
    return JsonResponse({"status": "ok"})


@csrf_exempt
@require_http_methods(['POST'])
def customer_shop_redact_request_webhook(request):

    shopify_hmac = request.META.get('HTTP_X_SHOPIFY_HMAC_SHA256')

    if not shopify_hmac:
        logger.warning("Missing HMAC header in shop redact webhook.")
        return HttpResponse("Missing signature", status=400)
    try:
        body = request.body
        expected_hmac = base64.b64encode(
            hmac.new(settings.SHOPIFY_API_SECRET.encode(),
                     body, hashlib.sha256).digest()
        ).decode()

        if not hmac.compare_digest(expected_hmac, shopify_hmac):
            logger.warning("Invalid HMAC signature.")
            return HttpResponse("Unauthorized", status=401)

        data = json.loads(body)
        shop_domain = data.get('shop_domain')
        if not shop_domain:
            logger.error("Shop domain missing in payload.")
            return HttpResponse("Bad request", status=400)
        try:
            shop = ShopifyStore.objects.get(shop_domain=shop_domain)
            user = CustomUser.objects.filter(custom_email=shop.email).first()

            shop.delete()
            if user:
                user.is_active = False
                user.shopify_connect = False
                user.scheduled_package = None
                user.package_plan = 1
                user.save()

            logger.info(f"Shopify store '{shop_domain}' deleted successfully.")
            return HttpResponse(status=200)

        except ShopifyStore.DoesNotExist:
            logger.warning(f"ShopifyStore not found for domain: {shop_domain}")
            return HttpResponse(status=404)
    except Exception as e:
        logger.exception("Unhandled error in shop redact webhook.")
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def debug_webhook(request):
    print("✅ Webhook dummy endpoint reached!")
    return JsonResponse({"status": "ok"})
