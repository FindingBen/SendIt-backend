import vonage
import logging
import phonenumbers
import hashlib
import json
import pytz
from datetime import timedelta
from base.models import Message, Element, AnalyticsData
from .models import Sms, CampaignStats
from celery import shared_task
from django_celery_beat.models import ClockedSchedule, PeriodicTask
from uuid import uuid4
from django.conf import settings
from django.utils import timezone
from django.utils.timezone import now
from django.db import transaction
from django.core.cache import cache
from notification.models import Notification
from base.email.email import send_email_notification
from .utils import price_util
from phonenumbers import geocoder


@shared_task
def send_scheduled_sms(unique_tracking_id: None):
    logger = logging.getLogger(__name__)
    try:
        from .models import Sms
        from base.models import CustomUser, ContactList, Message, Contact

        smsObj = Sms.objects.get(unique_tracking_id=unique_tracking_id)
        contact_list = ContactList.objects.get(id=smsObj.contact_list.id)
        message = Message.objects.get(id=smsObj.message.id)
        content_link = smsObj.content_link
        sms_text = smsObj.sms_text
        user = CustomUser.objects.get(id=smsObj.user.id)
        analytics_data = AnalyticsData.objects.get(custom_user=smsObj.user.id)
        elements = Element.objects.filter(message=message.id)
        button_count = 0

        for element in elements:
            if element.element_type == 'Button':
                button_count += 1
                setattr(
                    smsObj, f'button_{button_count}_name', element.button_title)
                smsObj.has_button = True
        smsObj.save()

        with transaction.atomic():
            if not smsObj.is_sent:

                client = vonage.Client(
                    key=settings.VONAGE_ID, secret=settings.VONAGE_TOKEN)
                sms = vonage.Sms(client)

                # Use self.contact_list to get the related ContactList instance
                contact_obj = Contact.objects.filter(
                    contact_list=contact_list)
                # Get value for total sms sends based on contact list length
                query_params = {
                    "api_key": settings.VONAGE_ID,
                    "api_secret": settings.VONAGE_TOKEN
                }
                country_prices = price_util.vonage_api_pricing(query_params)
                try:
                    for recipient in contact_obj:
                        phone_number = str(recipient.phone_number)
                        if not phone_number.startswith('+'):
                            phone_number = '+' + phone_number
                        parsed = phonenumbers.parse(phone_number)
                        country_code = geocoder.region_code_for_number(parsed)
                        price = country_prices.get(
                            country_code, country_prices.get("US", 0))
                        print('PRICE:', price)
                        if content_link:
                            message_text = sms_text.replace('#Link', content_link).replace('#FirstName', recipient.first_name) + \
                                "\n\n\n\n\n" + \
                                f'\nClick to Opt-out: {smsObj.unsubscribe_path}/{recipient.id}'
                        else:
                            message_text = sms_text.replace('#FirstName', recipient.first_name) + \
                                "\n\n\n\n\n" + \
                                f'\nClick to Opt-out: {smsObj.unsubscribe_path}/{recipient.phone_number}'

                        segments = price_util.calculate_sms_segments(
                            message_text)
                        total_cost = price * segments
                        encoded_price = int(total_cost * 10000)
                        client_ref = f"{country_code}-{encoded_price:04}-{unique_tracking_id}"
                        sms_kwargs = {
                            "from": '+12312345',
                            "to": phone_number,
                            "text": message_text,
                            "client-ref": client_ref  # includes price + country
                        }

                        responseData = sms.send_message(sms_kwargs)

                    smsObj.sms_sends = contact_list.contact_lenght
                    smsObj.save()
                    message.status = 'sent'
                    message.save()
                    smsObj.is_sent = True
                    analytics_data.total_sends += contact_list.contact_lenght
                    analytics_data.save()
                    cache_key = f"messages:{smsObj.user.id}"
                    cache.delete(cache_key)

                    if responseData["messages"][0]["status"] != "0":
                        message.status = 'error'
                        message.save()
                        Notification.objects.create(
                            user=user,
                            notif_type='error',
                            title='SMS Sending Error',
                            message=f"There has been an error while sending your sms!"
                        )
                        send_email_notification(user.id)
                        logger.error(
                            f"Message failed: {responseData['messages'][0].get('error-text', 'Unknown error')}")
                        return
                    scheduled_time_utc = now() + timedelta(days=3)
                    scheduled_time_utc = scheduled_time_utc.astimezone(
                        pytz.utc)

                    clocked, _ = ClockedSchedule.objects.get_or_create(
                        clocked_time=scheduled_time_utc)

                    PeriodicTask.objects.create(
                        name=f'archive-message-{uuid4()}',
                        task='sms.tasks.archive_message',
                        clocked=clocked,
                        one_off=True,
                        args=json.dumps([smsObj.id]),
                    )

                except Exception as e:
                    message.status = 'error'
                    message.save()
                    logger.exception("Error sending SMS")
                    Notification.objects.create(
                        user=user,
                        notif_type='error',
                        title='SMS Schedule Error',
                        message=f"There has been an error while scheduling your sms!"
                    )
                    send_email_notification(user.id)
                    raise

            else:
                logger.info(f"SMS {smsObj.id} already sent, skipping.")
    except Sms.DoesNotExist:
        logger.error(
            f"Sms with tracking id {unique_tracking_id} does not exist.")
    except Exception as e:
        logger.exception(f"Unhandled error in send_scheduled_sms: {str(e)}")


@shared_task
def send_sms(unique_tracking_id: None, user: None):
    logger = logging.getLogger(__name__)
    try:
        from .models import Sms
        from base.models import ContactList, Message, Contact, CustomUser
        smsObj = Sms.objects.get(unique_tracking_id=unique_tracking_id)
        user = smsObj.user
        analytics_data = AnalyticsData.objects.get(custom_user=user.id)
        contact_list = smsObj.contact_list
        message = smsObj.message
        content_link = smsObj.content_link
        sms_text = smsObj.sms_text
        elements = Element.objects.filter(message=message.id)

        button_count = 0

        for element in elements:
            if element.element_type == 'Button':
                button_count += 1
                setattr(
                    smsObj, f'button_{button_count}_name', element.button_title)
                smsObj.has_button = True
        smsObj.save()

        with transaction.atomic():
            if not smsObj.is_sent:
                client = vonage.Client(
                    key=settings.VONAGE_ID, secret=settings.VONAGE_TOKEN)
                sms = vonage.Sms(client)
                contact_obj = Contact.objects.filter(
                    contact_list=contact_list)
                # Get value for total sms sends based on contact list length
                query_params = {
                    "api_key": settings.VONAGE_ID,
                    "api_secret": settings.VONAGE_TOKEN
                }
                country_prices = price_util.vonage_api_pricing(query_params)
                for recipient in contact_obj:
                    phone_number = str(recipient.phone_number)
                    if not phone_number.startswith('+'):
                        phone_number = '+' + phone_number
                    parsed = phonenumbers.parse(phone_number)
                    country_code = geocoder.region_code_for_number(parsed)
                    price = country_prices.get(
                        country_code, country_prices.get("US", 0))
                    print('PRICE:', price)
                    if content_link:
                        message_text = sms_text.replace('#Link', content_link).replace('#FirstName', recipient.first_name) + \
                            "\n\n\n\n\n" + \
                            f'\nClick to Opt-out: {smsObj.unsubscribe_path}/{recipient.id}'
                    else:
                        message_text = sms_text.replace('#FirstName', recipient.first_name) + \
                            "\n\n\n\n\n" + \
                            f'\nClick to Opt-out: {smsObj.unsubscribe_path}/{recipient.phone_number}'

                    segments = price_util.calculate_sms_segments(
                        message_text)
                    total_cost = price * segments
                    encoded_price = int(total_cost * 10000)
                    client_ref = f"{country_code}-{encoded_price:04}-{unique_tracking_id}"
                    sms_kwargs = {
                        "from": '+12312345',
                        "to": phone_number,
                        "text": message_text,
                        "client-ref": client_ref  # includes price + country
                    }

                    responseData = sms.send_message(sms_kwargs)
                logger.info("VONAGE RESPONSE", responseData)
                smsObj.sms_sends = contact_list.contact_lenght
                smsObj.is_sent = True

                smsObj.save()
                message.status = 'sent'
                message.save()
                analytics_data.total_sends += contact_list.contact_lenght
                analytics_data.save()
                cache_key = f"messages:{smsObj.user.id}"
                cache.delete(cache_key)
                logger.info(
                    f"SMS {smsObj.id} sent successfully to {contact_list.contact_lenght} recipients.")
            else:
                logger.info(f"SMS {smsObj.id} already sent, skipping.")
    except Sms.DoesNotExist:
        logger.error(
            f"Sms with tracking id {unique_tracking_id} does not exist.")
    except Exception as e:
        logger.exception(f"Unhandled error in send_sms: {str(e)}")
        try:
            send_email_notification(user.id)
        except Exception:
            logger.error("Failed to send error notification email.")


def generate_hash(phone_number):
    # Create a hashlib object
    sha256 = hashlib.sha256()
    # Update the hash object with the phone number as bytes
    sha256.update(str(phone_number).encode('utf-8'))

    # Get the hexadecimal representation of the hash
    hashed_phone = sha256.hexdigest()

    return hashed_phone


@shared_task
def archive_message(sms_id):
    logger = logging.getLogger(__name__)
    try:
        with transaction.atomic():
            sms = Sms.objects.get(id=sms_id)
            message = sms.message  # Assuming Sms has a ForeignKey to Message
            logger.info(f"Archiving SMS {sms_id} and message {message.id}")
            if CampaignStats.objects.filter(message=message, user=sms.user).exists():
                logger.warning(
                    f"CampaignStats for SMS {sms_id} and message {message.id} already archived.")
                return 'Campaign already archived'
            message.status = 'archived'
            message.save()

            custom_user = sms.user
            custom_user.archived_state = True
            custom_user.save()

            total_clicks = (sms.click_button + sms.click_number)
            print('TOTAL_CLICKS', total_clicks)
            audience = sms.sms_sends
            total_views = sms.total_views
            unsub_users = 0
            # Weights for performance calculation
            w1 = 0.4  # Weight for total views
            w2 = 0.6  # Weight for total clicks
            w3 = 0.1  # Weight for unsubscribes

            # Performance calculation based on the provided formula
            if audience > 0:
                overall_performance = (
                    (total_views / audience) * w1 +
                    (total_clicks / audience) * w2 -
                    (unsub_users / audience) * w3
                )
            else:
                overall_performance = 0

            # Convert performance to a percentage (out of 100)
            overall_performance = int(overall_performance * 100)

            campaign_stats = CampaignStats.objects.create(
                message=message,
                user=sms.user,
                name=message.message_name,
                engagement=total_views,
                total_clicks=total_clicks,
                audience=audience,
                unsub_users=unsub_users,
                overall_perfromance=overall_performance,  # Store the calculated performance
                campaign_start=sms.created_at,
                campaign_end=timezone.now()  # Assuming the archive happens at the end
            )

            campaign_stats.save()
            sms.delete()
            Notification.objects.create(
                user=sms.user,
                title='Campaign arvhived successfully',
                notif_type='success',
                message=f"Your campaign got archived successfully. You can view the stats in your dashboard.",
            )
            return 'Message archived successfully'
    except Sms.DoesNotExist:
        logger.error(f'SMS with id {sms_id} does not exist')
        return f'SMS with id {sms_id} does not exist'
    except Message.DoesNotExist:
        logger.error(f'Message related to SMS id {sms_id} does not exist')
        return f'Message related to SMS id {sms_id} does not exist'
    except Exception as e:
        logger.exception(
            f'An error occurred while archiving SMS {sms_id}: {str(e)}')
        return f'An error occurred: {str(e)}'
