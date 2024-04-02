from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .models import Sms
import time
from django.views.decorators.csrf import csrf_exempt
from base.models import Message, ContactList, CustomUser
from base.serializers import MessageSerializer
from .serializers import SmsSerializer
from django.http import HttpResponseRedirect, JsonResponse
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
        recipient_list = ContactList.objects.get(
            id=request.data['contact_list'])

        if user_obj.sms_count >= recipient_list.contact_lenght:

            if serializer.is_valid():

                sms = serializer.save()
                sms_result_task = send_sms.delay(
                    sms.unique_tracking_id, user_obj.id)

                time.sleep(4)
                if sms_result_task.ready():
                    try:
                        # If you need to handle different statuses, you can check them here
                        if sms_result_task.successful():
                            print('test')

                        else:
                            return Response({'error': 'There has been a system error. Contact support for more help.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

                    except ValueError as ve:
                        return Response({'error': 'There has been a system error. Contact support for more help.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
                    except Exception as e:
                        return Response({'error': 'There has been a system error. Contact support for more help.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
                else:
                    return Response({'error': 'Its taking longer then excpected..Contact support for more information'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
                return Response({
                    "sms": SmsSerializer(sms, context=self.get_serializer_context()).data
                })
        elif user_obj.sms_count < 0:
            return Response({'error': 'You have insufficient credit amount to cover this send. Top up your credit'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
        else:
            return Response({'error': 'You dont have enough credit amount to cover this send. Top up your credit'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)


@api_view(['POST'])
def schedule_sms(request):

    try:
        data = request.data
        user_obj = CustomUser.objects.get(id=request.data['user'])
        recipient_list = ContactList.objects.get(
            id=request.data['contact_list'])
        if user_obj.sms_count >= recipient_list.contact_lenght:

            with transaction.atomic():
                scheduled_time = datetime.fromisoformat(
                    str(request.data['scheduled_time']))
                print(scheduled_time)
                scheduled_time_utc = pytz.timezone(
                    'UTC').localize(scheduled_time)
                print('utc', scheduled_time_utc)
                # Get the local time zone
                # Provide your local timezone here
                local_timezone = pytz.timezone('GMT+2')
                print('local', local_timezone)
                # Convert scheduled time to the local time zone
                scheduled_time_local = scheduled_time_utc.astimezone(
                    local_timezone)

                # Check if daylight saving time is in effect for the scheduled time
                is_dst = scheduled_time_local.dst() != timedelta(0)
                print(is_dst)
                # Adjust for the time zone difference accounting for daylight saving time
                if is_dst:
                    scheduled_time_local -= timedelta(hours=1)
                    print('last', scheduled_time_local)
                current_datetime = datetime.now()
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

                    send_scheduled_sms.apply_async(
                        (sms.unique_tracking_id,), eta=scheduled_time_utc)

                    return Response({
                        "sms": f'{data}'
                    })
                else:
                    return Response({'error': 'Scheduled time must be in the future.'}, status=status.HTTP_400_BAD_REQUEST)
        elif user_obj.sms_count < 0:
            return Response({'error': 'You have insufficient credit amount to cover this send. Top up your credit'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

        else:
            return Response({'error': 'You dont have enough credit amount to cover this send. Top up your credit'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    except Exception as e:
        return Response({'There has been an error:': str(e)}, status=status.HTTP_405_METHOD_NOT_ALLOWED)


@api_view(['GET'])
def track_link_click(request, uuid):

    sms_obj = Sms.objects.get(unique_tracking_id=uuid)
    message_obj = Message.objects.get(id=sms_obj.message.id)
    sms_obj.click_number += 1  # Increment click_number by 1
    sms_obj.save()

    redirect_url = f"https://spplane.app/view/{message_obj.id}"
    return HttpResponseRedirect(redirect_url)


@csrf_exempt
@api_view(['POST'])
def vonage_webhook(request):
    try:
        # Parse the JSON data from the request body
        data = request.data
        sms_object = Sms.objects.get(unique_tracking_id=data['client-ref'])
        with transaction.atomic():
            user = sms_object.user
            # Do some other condition which checks weather the same number already passed
            if data['status'] == 'delivered':
                sms_object.delivered += 1
                user.sms_count -= 1

            elif data['status'] == 'failed':
                sms_object.not_delivered += 1
            elif data['status'] == 'rejected':
                sms_object.not_delivered += 1

            user.save()
            sms_object.save()

        print('Received Vonage Delivery Receipt:')

        # Respond with a success message
        return JsonResponse({'message': 'Delivery receipt received successfully'}, status=200)

    except Exception as e:
        print('Error handling Vonage delivery receipt:', str(e))

        return JsonResponse({'error': 'Error processing delivery receipt'}, status=200)
