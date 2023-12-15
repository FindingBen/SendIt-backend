from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .serializers import MessageSerializer, RegisterSerializer, CustomUserSerializer, ContactListSerializer, ContactSerializer, ElementSerializer, PackageSerializer
from .models import Message, ContactList, Contact, Element, PackagePlan, CustomUser, EmailConfirmationToken, SurveyResponse
from rest_framework import generics
from .utils.googleAnalytics import sample_run_report
from .email.email import send_confirmation_email, send_welcome_email
from django.db.models import Sum
import time


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        print(user)
        # Add custom claims
        token['username'] = user.username
        token['first_name'] = user.first_name
        token['last_name'] = user.last_name

        try:
            custom_user = CustomUser.objects.get(username=user.username)
            serialized_data = custom_user.serialize_package_plan()

            token['package_plan'] = serialized_data
        except CustomUser.DoesNotExist:
            token['package_plan'] = None

        return token


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

    def validate(self, **kwargs):
        pass


class SendEmailConfirmationTokenAPIView(APIView):

    # permission_classes = [IsAuthenticated]

    def post(self, request, format=None):

        user = request.data['user']['id']

        user_instance = CustomUser.objects.get(id=user)
        print(user_instance)
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
        from sms.models import Sms
        user = request.user
        notes = user.message_set.all()
        custom_user = CustomUser.objects.get(id=user.id)
        sms = Sms.objects.all()

        total_views = sms.aggregate(Sum('total_views'))[
            'total_views__sum'] or 0
        overall_perf = sms.aggregate(Sum('total_overall_rate'))[
            'total_overall_rate__sum'] or 0
        bounce_rate = sms.aggregate(Sum('total_bounce_rate'))[
            'total_bounce_rate__sum'] or 0

        sent_message_count = notes.filter(status='sent').count()

        serializer = MessageSerializer(notes, many=True)
    except Exception as e:
        return Response(f'There has been some error: {e}')
    return Response({"messages": serializer.data, "messages_count": sent_message_count, "total_values": {"total_views": total_views, "overall_perf": overall_perf, "bounce_rate": bounce_rate}})

# Contact lists


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_packages(request):
    try:
        package = PackagePlan.objects.all()
        serializer = PackageSerializer(package, many=True)
        data = serializer.data
    except Exception as e:
        return Response(f'There has been some error: {e}')
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_contact_lists(request):
    try:
        user = request.user
        contact_list = user.contactlist_set.all()

        serializer = ContactListSerializer(contact_list, many=True)
    except Exception as e:
        return Response(f'There has been some error: {e}')
    return Response(serializer.data)


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
        contact_list = ContactList.objects.get(id=id)
        contact = Contact.objects.filter(contact_list=contact_list)
        serializer = ContactSerializer(contact, many=True)
    except Exception as e:
        return Response(f'There has been some error: {e}')
    return Response(serializer.data)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_message(request, id):
    try:
        message = Message.objects.get(id=id)
        serializer = MessageSerializer(message, data=request.data)
        if serializer.is_valid(raise_exception=True):
            serializer.update(message, validated_data=request.data)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(f'There has been some error: {e}')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_contact(request, id):
    try:
        contact_list = ContactList.objects.get(id=id)
        serializer = ContactSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            serializer.save(contact_list=contact_list)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(f'There has been some error: {e}')


@api_view(['GET'])
def handle_unsubscribe(request, id):
    try:
        contact = Contact.objects.get(hashed_phone=id)
        contact.delete()
        return Response('Contact deleted successfully', status=status.HTTP_200_OK)
    except Exception as e:
        print(f'Error occurred while deleting contact: {e}')
        return Response(f'There has been an error: {e}', status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def purchase_package(request, id):
    try:
        user = CustomUser.objects.get(id=id)
        package_plan = PackagePlan.objects.get(id=request.data['package_plan'])

        user.package_plan = package_plan
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
            })
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CreateNote(generics.GenericAPIView):
    serializer_class = MessageSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = serializer.save()

        return Response({
            "note": MessageSerializer(message, context=self.get_serializer_context()).data
        })


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
        return Response(f'There has been some error: {e}')


class CreateElement(generics.GenericAPIView):
    serializer_class = ElementSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        element = serializer.save()
        if element.element_type == 'Survey':
            element.save_response()
        return Response({
            "element": ElementSerializer(element, context=self.get_serializer_context()).data
        })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_message(request, id):

    try:
        message = Message.objects.get(id=id)
        message.delete()
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

    start_date = request.query_params.get('startDate')
    end_date = request.query_params.get('endDate')
    analytics_data = sample_run_report(
        record_id=record_id, start_date=start_date, end_date=end_date)

    return Response({'message': 'Data returned!', 'data': analytics_data})


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
