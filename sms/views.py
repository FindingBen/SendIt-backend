import time
import pytz
import json
from django.conf import settings
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .models import Sms, CampaignStats
from django.utils.timezone import is_aware, make_aware, localtime
from django.views.decorators.csrf import csrf_exempt
from base.models import Message, ContactList, Contact, CustomUser, Element, AnalyticsData
from base.serializers import MessageSerializer
from .serializers import SmsSerializer, CampaignStatsSerializer
from django.http import HttpResponseRedirect, JsonResponse
from django.db import transaction
from datetime import datetime, timedelta
from .tasks import send_scheduled_sms, send_sms, archive_message
from django.utils import timezone
from django.utils.timezone import make_aware
from notification.models import Notification
from .utils import price_util
from uuid import uuid4
from django_celery_beat.models import PeriodicTask, ClockedSchedule


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
        contact_list = ContactList.objects.get(
            id=request.data['contact_list'])
        contact_obj = Contact.objects.filter(
            contact_list=contact_list)
        query_params = {
            "api_key": settings.VONAGE_ID,
            "api_secret": settings.VONAGE_TOKEN,

        }
        pricing_info = price_util.get_price_per_segment(
            contact_obj, request.data['sms_text'], query_params)

        if user_obj.sms_count >= pricing_info.get('estimated_credits', None):

            if serializer.is_valid():

                sms = serializer.save()

                sms_result_task = send_sms.delay(
                    sms.unique_tracking_id, user_obj.id)
                time.sleep(2)
                scheduled_time_utc = (
                    now() + timedelta(days=3)).astimezone(pytz.utc)

                clocked, _ = ClockedSchedule.objects.get_or_create(
                    clocked_time=scheduled_time_utc)

                PeriodicTask.objects.create(
                    name=f'archive-message-{uuid4()}',
                    task='sms.tasks.archive_message',
                    clocked=clocked,
                    one_off=True,
                    args=json.dumps([smsObj.id]),
                )

                if sms_result_task:
                    try:
                        # If you need to handle different statuses, you can check them here
                        Notification.objects.create(
                            user=user_obj,
                            title='Sms sent successfully',
                            notif_type='success',
                            message=f"You just executed successfully a sms transaction!"
                        )
                        return Response({
                            "sms": "Successfully sent!"}, status=status.HTTP_200_OK)
                    except ValueError as ve:
                        return Response({'error': 'There has been a system error. Contact support for more help.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
                    except Exception as e:
                        return Response({'error': 'There has been a system error. Contact support for more help.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
                else:
                    return Response({'error': 'Its taking longer then excpected..Contact support for more information'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
        elif user_obj.sms_count < 0:
            return Response({'error': 'You have insufficient credit amount to cover this send. Top up your credit'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
        else:
            return Response({'error': 'You dont have enough credit amount to cover this send. Top up your credit'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_campaign_stats(request):
    try:
        today = timezone.now().date()
        user = request.user
        show_all = request.query_params.get('all', 'false').lower() == 'true'
        limit = request.query_params.get('limit', 'false').lower() == 'true'
        best_perf = request.query_params.get(
            'best_perf', 'false').lower() == 'true'
        if show_all:
            campaigns = CampaignStats.objects.filter(user=user)
        elif limit:
            campaigns = CampaignStats.objects.filter(
                user=user, campaign_end__lte=today)[:6]
        elif best_perf:
            campaigns = CampaignStats.objects.filter(
                user=user, campaign_end__lte=today
            ).order_by('-overall_perfromance')[:4]
        serializer = CampaignStatsSerializer(campaigns, many=True)
    except Exception as e:
        return Response(f'There has been an error: {e}')

    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
def schedule_sms(request):

    try:
        data = request.data
        user_obj = CustomUser.objects.get(id=request.data['user'])
        recipient_list = ContactList.objects.get(
            id=request.data['contact_list'])
        contact_obj = Contact.objects.filter(
            contact_list=recipient_list)
        query_params = {
            "api_key": settings.VONAGE_ID,
            "api_secret": settings.VONAGE_TOKEN,

        }
        pricing_info = price_util.get_price_per_segment(
            contact_obj, request.data['sms_text'], query_params)
        if user_obj.sms_count >= pricing_info.get('estimated_credits', None):

            with transaction.atomic():
                copenhagen_tz = pytz.timezone('Europe/Copenhagen')

                # Parse the scheduled time from the request and assume it's in Copenhagen time
                scheduled_time_local = make_aware(
                    datetime.fromisoformat(request.data['scheduled_time']),
                    timezone=copenhagen_tz
                )

                # Convert scheduled time to UTC
                scheduled_time_utc = scheduled_time_local.astimezone(pytz.utc)

                # Get the current UTC time
                current_datetime_utc = datetime.now(pytz.utc)

                # Debugging print
                print("Scheduled Time UTC:", scheduled_time_utc)
                print("Current Time UTC:", current_datetime_utc)

                # Get the current UTC time
                current_datetime_utc = datetime.now(pytz.utc)
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

                if scheduled_time_utc > current_datetime_utc:
                    message.status = 'Scheduled'

                    message.save()
                    scheduled_time_utc = scheduled_time_utc.replace(
                        microsecond=0)

                    clocked, _ = ClockedSchedule.objects.get_or_create(
                        clocked_time=scheduled_time_utc)

                    PeriodicTask.objects.create(
                        # unique name
                        name=f'send-scheduled-sms-{sms.unique_tracking_id}',
                        task='sms.tasks.send_scheduled_sms',
                        clocked=clocked,
                        one_off=True,
                        args=json.dumps([sms.unique_tracking_id]),
                    )
                    Notification.objects.create(
                        user=user_obj,
                        title='Sms scheduled successfully',
                        notif_type='success',
                        message=f"You just executed successfully a sms schedule transaction!"
                    )
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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_scheduled_sms(request):
    message_id = request.data.get('message_obj')
    sms = Sms.objects.get(message_id=message_id)
    if not message_id:
        return Response({"error": "Missing message_id"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        print(sms.unique_tracking_id)
        # 1. Find and delete the scheduled task
        task_name = f'send-scheduled-sms-{sms.unique_tracking_id}'
        task = PeriodicTask.objects.get(name=task_name)
        clocked_id = task.clocked_id
        task.delete()

        # # 2. Optionally delete the clocked schedule if no other task uses it
        if not PeriodicTask.objects.filter(clocked_id=clocked_id).exists():
            ClockedSchedule.objects.filter(id=clocked_id).delete()

        with transaction.atomic():
            sms.delete()

            message = sms.message
            message.status = 'Draft'
            message.save()

        return Response({"success": "Scheduled SMS cancelled."}, status=status.HTTP_200_OK)

    except PeriodicTask.DoesNotExist:
        return Response({"error": "Scheduled task not found."}, status=status.HTTP_404_NOT_FOUND)
    except Sms.DoesNotExist:
        return Response({"error": "SMS object not found."}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def track_link_click(request, id):
    print(request)
    try:
        sms_obj = Sms.objects.get(message=id)
        analytics_data = AnalyticsData.objects.get(custom_user=sms_obj.user.id)

        message_obj = Message.objects.get(id=sms_obj.message.id)
        with transaction.atomic():
            sms_obj.click_number += 1  # Increment click_number by 1
            sms_obj.save()
            analytics_data.total_clicks += 1
            analytics_data.save()
        redirect_url = f"https://spplane.app/view/{message_obj.id}"
        return HttpResponseRedirect(redirect_url)
    except Exception as e:
        return HttpResponseRedirect('https://spplane.app/err/spp/')


@api_view(['GET'])
def track_button_click(request, id):
    try:
        print('Button ID:', id)
        # my el object
        element = Element.objects.get(unique_button_id=id)
        redirect_url = element.button_link
        if not redirect_url.startswith(('http://', 'https://')):
            redirect_url = 'http://' + redirect_url
        sms_obj = Sms.objects.get(message=element.message.id)
        analytics_data = AnalyticsData.objects.get(custom_user=sms_obj.user.id)
        elements = Element.objects.filter(
            message=element.message.id, element_type='Button')
        button_index = None

        # Loop through the buttons to find the index of the clicked button
        for index, btn_element in enumerate(elements, start=1):
            if btn_element.unique_button_id == id:
                button_index = index
                break

        if button_index is not None:
            with transaction.atomic():
                setattr(sms_obj, f'button_{button_index}', getattr(
                    sms_obj, f'button_{button_index}', 0) + 1)
                sms_obj.click_button += 1  # General click count
                sms_obj.save()
                analytics_data.total_clicks += 1
                analytics_data.save()
        else:
            print('No matching button found')
        return HttpResponseRedirect(redirect_url)
    except Exception as e:
        return Response(f'There has been error retrieving the object: {e}')


@csrf_exempt
@api_view(['POST'])
def vonage_webhook(request):
    try:
        # Parse the JSON data from the request body
        data = request.data
        ref = data.get('client-ref', '')
        print('AAAAAA')
        country_code, encoded_price, short_tracking_id = ref.split("-")
        price = int(encoded_price) / 10000.0
        credits_to_deduct = int(round(price * 100))
        unique_tracking_id = short_tracking_id
        sms_object = Sms.objects.get(unique_tracking_id=unique_tracking_id)
        if not ref or '-' not in ref:
            return JsonResponse({'error': 'Invalid client-ref'}, status=400)

        with transaction.atomic():
            user = sms_object.user
            analytics = AnalyticsData.objects.get(custom_user=user.id)
            user.sms_count -= credits_to_deduct
            print('DEDUCTED!! GODAMN')
            # Do some other condition which checks weather the same number already passed
            if data['status'] == 'delivered':
                sms_object.delivered += 1
                analytics.total_delivered += 1

            elif data['status'] == 'failed':
                sms_object.not_delivered += 1
                analytics.total_not_delivered += 1
            elif data['status'] == 'rejected':
                sms_object.not_delivered += 1
                analytics.total_not_delivered += 1

            analytics.save()
            user.save()
            sms_object.save()

        print('Received Vonage Delivery Receipt:')

        # Respond with a success message
        return JsonResponse({'message': 'Delivery receipt received successfully'}, status=200)

    except Exception as e:
        print('Error handling Vonage delivery receipt:', str(e))

        return JsonResponse({'error': 'Error processing delivery receipt'}, status=200)


@csrf_exempt
@api_view(['POST'])
def vonage_webhook_message(request):
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


@api_view(['POST'])
# @permission_classes([IsAuthenticated])
def get_outbound_pricing(request):
    try:
        list_id = request.data['id']
        sms_text = request.data['sms_text']

        # Check shopify documentation regarding contact lists and recipients

        contact_obj = Contact.objects.filter(
            contact_list=list_id)

        query_params = {
            "api_key": settings.VONAGE_ID,
            "api_secret": settings.VONAGE_TOKEN,

        }
        pricing_info = price_util.get_price_per_segment(
            contact_obj, sms_text, query_params)

        return Response(pricing_info, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": f"There has been am error {e}"}, status=status.HTTP_400_BAD_REQUEST)


def schedule_archive_task(sms_id, scheduled_time):
    try:
        print("SSS", scheduled_time, type(scheduled_time))

        # Ensure scheduled_time is timezone-aware in Europe/Copenhagen
        copenhagen_tz = pytz.timezone('Europe/Copenhagen')
        if not is_aware(scheduled_time):
            scheduled_time = make_aware(scheduled_time, timezone=copenhagen_tz)
        else:
            scheduled_time = scheduled_time.astimezone(copenhagen_tz)

        archive_time_aware = scheduled_time + timedelta(minutes=5)
        # Add 5 minutes for testing (or 5 days in production)
        archive_time_naive = archive_time_aware.replace(tzinfo=None)

        print('ARCHIVE_TIME (Copenhagen):', archive_time_naive)

        # Schedule task using local time directly
        archive_message.apply_async((sms_id,), countdown=300)
        print("scheduled for archive")
    except Exception as e:
        print("Error in schedule_archive_task:", e)
