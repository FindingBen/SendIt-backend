from math import ceil
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .serializers import MessageSerializer, RegisterSerializer, CustomUserSerializer, ContactListSerializer, ContactSerializer, ElementSerializer, PackageSerializer, SurveySerializer
from .models import Message, ContactList, Contact, Element, PackagePlan, CustomUser, EmailConfirmationToken, SurveyResponse
from rest_framework import generics
from sms.models import Sms
from .utils.googleAnalytics import sample_run_report
from .email.email import send_confirmation_email, send_welcome_email
from django.db.models import Sum
from sms.models import Sms
from datetime import datetime
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.conf import settings
from base.utils.calculations import calculate_avg_performance


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
            serialized_data = custom_user.serialize_package_plan()
            token['sms_count'] = custom_user.sms_count
            token['user_type'] = custom_user.user_type
            token['package_plan'] = serialized_data
            token['custom_email'] = custom_user.custom_email
        except CustomUser.DoesNotExist:
            token['package_plan'] = None

        return token


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

    def validate(self, **kwargs):
        pass


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
        token = EmailConfirmationToken.objects.get(pk=token_id)
        user = token.user
        user.is_active = True
        user.save()
        if user.is_active is True:
            send_welcome_email(user.email, user)
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
    user = CustomUser.objects.get(id=id)
    serializer = CustomUserSerializer(user, data=request.data, partial=True)
    if serializer.is_valid(raise_exception=True):

        serializer.update(user, validated_data=request.data)
        return Response(serializer.data, status=status.HTTP_200_OK)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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
        archive = request.GET.get('archive', None)

        sort_by = request.GET.get('sort_by', None)

        if archive == 'true':
            # Fetch only archived messages
            notes = user.message_set.filter(status='archived')
            serializer = MessageSerializer(notes, many=True)
            serialized_data = serializer.data
            return Response({"messages": serialized_data})

        # By default, filter by 'sent' status and exclude archived messages
        notes = user.message_set.exclude(status='archived')

        if sort_by:
            # If sorting is applied, apply sorting
            notes = notes.order_by(sort_by)
            print('here?')
        # Exclude archived messages again after sorting, if applicable
        notes = notes.exclude(status='archived')
        print('not archived', notes)
        # Cou  nt the sent messages
        sent_message_count = notes.filter(status='sent').count()

        serializer = MessageSerializer(notes, many=True)
        serialized_data = serializer.data

        return Response({"messages": serialized_data, "messages_count": sent_message_count})

    except Exception as e:
        return Response(f'There has been some error: {e}')


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
    contact_list = user.contactlist_set.all()

    recipients = Contact.objects.filter(users=user)
    recipients_serializer = ContactSerializer(recipients, many=True)
    package_limits = {
        'Gold package': {'contact_lists': 20, 'recipients': 10000},
        'Silver package': {'contact_lists': 8, 'recipients': 5000},
        'Basic package': {'contact_lists': 5, 'recipients': 1000},
        'Trial Plan': {'contact_lists': 1, 'recipients': 5}
    }

    # Get the user's package plan
    # Replace 'package_plan' with the actual attribute name
    user_package = user.package_plan
    # Get the limits based on the user's package plan
    if user_package.plan_type in package_limits:
        limits = package_limits[user_package.plan_type]
    else:
        # Default to Trial package if user's package is not recognized
        limits = package_limits['Trial Plan']
    serializer = ContactListSerializer(contact_list, many=True)
    # except Exception as e:
    #     return Response(f'There has been some error: {e}')
    return Response({"data": serializer.data, "limits": limits, "recipients": recipients_serializer.data})


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
        user = request.user
        contact_list = ContactList.objects.get(id=id)
        cache_key = f"user_contacts:{contact_list.id}"

        # Check for sorting query parameters
        sort_by = request.GET.get('sort_by', None)
        if sort_by and sort_by not in ['first_name', '-first_name', 'created_at', '-created_at']:
            sort_by = ''

        # Check if sorting parameters are present
        if sort_by:
            contact_list = ContactList.objects.get(id=id)
            contact = Contact.objects.filter(contact_list=contact_list)

            # Apply sorting to the queryset
            contact = contact.order_by(sort_by)

            serializer = ContactSerializer(contact, many=True)

            # Cache the sorted data
            cache.set(cache_key, {"contacts": serializer.data},
                      timeout=settings.CACHE_TTL)

            return Response({"contacts": serializer.data})
        else:
            # Sorting parameters are not present, check the cache
            cached_data = cache.get(cache_key)

            if cached_data is None:
                # Data is not in the cache, fetch from the database without sorting

                contact_list = ContactList.objects.get(id=id)
                contact = Contact.objects.filter(contact_list=contact_list)

                serializer = ContactSerializer(contact, many=True)

                # Cache the data without sorting
                cache.set(
                    cache_key, {"contacts": serializer.data}, timeout=settings.CACHE_TTL)

                return Response({"contacts": serializer.data})
            else:
                # Data is in the cache, use the cached data without querying the database
                contacts = cached_data['contacts']

                return Response({"contacts": contacts})

    except Exception as e:
        return Response(f'There has been some error: {e}')


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def contact_detail(request, id):
    try:
        contact = Contact.objects.get(id=id)

    except Contact.DoesNotExist:
        return Response({"error": "Contact not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = ContactSerializer(contact)
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method == 'PUT':
        serializer = ContactSerializer(
            contact, data=request.data, partial=True)
        if serializer.is_valid():
            cache_key = f"user_contacts:{request.user.id}"
            cache.delete(cache_key)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_message(request, id):
    try:
        message = Message.objects.get(id=id)
        print(request.data)
        serializer = MessageSerializer(
            message, data=request.data, partial=True)
        if serializer.is_valid(raise_exception=True):
            serializer.update(message, validated_data=request.data)
            print('AAAA', serializer.data)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(f'There has been some error: {e}')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_contact(request, id):
    trial_limit = 10
    basic_limit = 1000
    silver_limit = 3000
    gold_limit = 8000
    try:

        custom_user = CustomUser.objects.get(id=request.user.id)
        contacts = Contact.objects.filter(users=request.user.id)
        package_plan = custom_user.package_plan
        print(len(contacts))
        if package_plan.plan_type == 'Basic package':
            if len(contacts) < basic_limit:
                contact_list = ContactList.objects.get(id=id)
                serializer = ContactSerializer(data=request.data)
            else:
                return Response({"Error, max number of recipients reached! Upgrade your package."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
        elif package_plan.plan_type == 'Silver package':
            if len(contacts) < silver_limit:
                contact_list = ContactList.objects.get(id=id)
                serializer = ContactSerializer(data=request.data)
            else:
                return Response({"Error, max number of recipients reached! Upgrade your package."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
        elif package_plan.plan_type == 'Gold package':
            if len(contacts) < gold_limit:
                contact_list = ContactList.objects.get(id=id)
                serializer = ContactSerializer(data=request.data)
            else:
                return Response({"Error, max number of recipients reached! Upgrade your package."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
        else:
            if len(contacts) < trial_limit:
                contact_list = ContactList.objects.get(id=id)
                serializer = ContactSerializer(data=request.data)
            else:
                return Response({"Error, max number of recipients reached! Upgrade your package."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
        if serializer.is_valid(raise_exception=True):
            # print(serializer.validated_data)
            if not request.data['first_name'] and request.data['phone_number']:
                return Response({'error': 'Empty form submission.'}, status=status.HTTP_400_BAD_REQUEST)

            serializer.save(contact_list=contact_list, users=request.user)

            cache_key = f"user_contacts:{contact_list.id}"
            cache.delete(cache_key)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    except Exception as e:
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
        contact = Contact.objects.get(id=id)
        contact.delete()
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
        return Response("Field cannot be blank", status=status.HTTP_400_BAD_REQUEST)


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


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_contact_recipient(request, id):
    try:
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
def get_analytics_data(request, record_id):
    sms = Sms.objects.get(message=record_id)

    start_date = sms.created_at
    end_date = datetime.now().date()
    analytics_data, periodic_data = sample_run_report(
        record_id=record_id, start_date=start_date, end_date=end_date, recipients=sms.sms_sends)
    avg_data_calc = calculate_avg_performance(periodic_data)
    print("AAAA", len(periodic_data))
    return Response({'message': 'Data returned!', 'data': analytics_data, 'period_data': periodic_data, "avg_data": avg_data_calc})


@api_view(['GET'])
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
def get_total_analytic_values(request, id):
    total_values = Sms.objects.filter(user=id).aggregate(
        total_bounce_rate=Sum('total_bounce_rate'),
        total_overall_rate=Sum('total_overall_rate'),
        total_views=Sum('total_views'),
        total_sends=Sum('sms_sends')
    )

    # If there are no matching Sms objects, set default values to 0
    total_bounce_rate = total_values['total_bounce_rate'] or 0
    total_overall_rate = total_values['total_overall_rate'] or 0
    total_views = total_values['total_views'] or 0
    total_sends = total_values['total_sends'] or 0
    average_bounce_rate = round(
        total_bounce_rate / total_sends, 2) if total_sends > 0 else None
    average_overall_rate = round(
        total_overall_rate / total_sends, 2) if total_sends > 0 else None

    return Response({
        'average_bounce_rate': average_bounce_rate,
        'average_overall_rate': average_overall_rate,
        'total_views': total_views,
        'total_sends': total_sends
    })


@api_view(['PUT'])
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
