from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .models import Sms
from django.views.decorators.csrf import csrf_exempt
from base.models import Message, ContactList, CustomUser
from base.serializers import MessageSerializer
from .serializers import SmsSerializer
from rest_framework import generics
from django.http import JsonResponse
from django.http import HttpResponseRedirect
from django.db import transaction
from datetime import datetime, timedelta
import pytz
from .tasks import send_scheduled_sms, send_sms


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_message(request, id):
    try:
        message = Message.objects.get(id=id)
        serializer = MessageSerializer(message)
    except Exception as e:
        return Response(f'There has been an error: {e}')

    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_sms(request, id):
    try:
        sms = Sms.objects.get(message_id=id)
        serializer = SmsSerializer(sms)
    except Exception as e:
        return Response(f'There has been an error: {e}')

    return Response(serializer.data, status=status.HTTP_200_OK)


class createSms(generics.GenericAPIView):
    serializer_class = SmsSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_obj = CustomUser.objects.get(id=request.data['user'])

        if user_obj.sms_count > 0:
            if serializer.is_valid():

                sms = serializer.save()
                print(sms.unique_tracking_id)
                send_sms.delay(sms.unique_tracking_id)
                return Response({
                    "sms": SmsSerializer(sms, context=self.get_serializer_context()).data
                })
        else:
            return Response({'error': 'You have no sms credit left, purchase a new package or extend the current one'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)


@api_view(['POST'])
def schedule_sms(request):

    try:
        data = request.data
        user_obj = CustomUser.objects.get(id=request.data['user'])

        if user_obj.sms_count > 0:

            with transaction.atomic():
                scheduled_time = datetime.fromisoformat(
                    str(request.data['scheduled_time']))
                scheduled_time_utc = pytz.timezone(
                    'UTC').localize(scheduled_time)
                # Adjust for the time zone difference (2 hours ahead)
                scheduled_time_local = scheduled_time_utc - timedelta(hours=2)
                current_datetime = datetime.fromisoformat(
                    str(datetime.now()))

                custom_user = CustomUser.objects.get(id=data['user'])
                contact_list = ContactList.objects.get(id=data['contact_list'])

                message = Message.objects.get(id=data['message'])

                sms_sends = contact_list.contact_lenght
                sms = Sms(
                    user=custom_user,
                    sender=data['sender'],
                    sms_text=data['sms_text'],
                    content_link=data['content_link'],
                    contact_list=contact_list,
                    message=message,
                    sms_sends=sms_sends,
                    scheduled_time=data['scheduled_time'],
                )

                sms.save()

                if scheduled_time > current_datetime:
                    message.status = 'Scheduled'
                    message.save()
                    # Schedule the SMS to be sent in the future
                    send_scheduled_sms.apply_async(
                        (sms.unique_tracking_id,), eta=scheduled_time_local)

                    return Response({
                        "sms": f'{data}'
                    })
                else:
                    return Response({'error': 'Scheduled time must be in the future.'}, status=status.HTTP_400_BAD_REQUEST)

        else:
            return Response({'error': 'You have no SMS credit left, purchase a new package or extend the current one'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    except:
        print('There has been an error')
    return Response('failed')


@api_view(['GET'])
def track_link_click(request, uuid):

    sms_obj = Sms.objects.get(unique_tracking_id=uuid)

    message_obj = Message.objects.get(id=sms_obj.message.id)

    sms_obj.click_number += 1  # Increment click_number by 1
    sms_obj.save()

    # # Return a JSON response indicating that the click was recorded
    # # Replace with your desired URL
    redirect_url = f"https://sendit-frontend-production.up.railway.app/message_view/{message_obj.id}"
    return HttpResponseRedirect(redirect_url)


@csrf_exempt
@api_view(['POST'])
def vonage_webhook(request):
    try:
        # Parse the JSON data from the request body
        data = request.data
        sms_object = Sms.objects.get(unique_tracking_id=data['client-ref'])
        with transaction.atomic():
            if data['status'] == 'delivered':
                sms_object.delivered += 1

            elif data['status'] == 'failed':
                sms_object.not_delivered += 1
            elif data['status'] == 'rejected':
                sms_object.not_delivered += 1

            sms_object.save()

        print('Received Vonage Delivery Receipt:')

        # Respond with a success message
        return JsonResponse({'message': 'Delivery receipt received successfully'}, status=200)

    except Exception as e:
        print('Error handling Vonage delivery receipt:', str(e))

        return JsonResponse({'error': 'Error processing delivery receipt'}, status=200)
