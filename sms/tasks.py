from __future__ import absolute_import, unicode_literals
from datetime import timedelta
from base.models import Message, Element, AnalyticsData
from .models import Sms, CampaignStats
from celery import shared_task
import vonage
from django.conf import settings
from django.utils import timezone
import uuid
from django.db import transaction
import hashlib
from django.core.cache import cache
from base.email.email import send_email_notification


@shared_task
def send_scheduled_sms(unique_tracking_id: None):

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
        button_count = 0

        with transaction.atomic():
            if not smsObj.is_sent:

                client = vonage.Client(
                    key=settings.VONAGE_ID, secret=settings.VONAGE_TOKEN)
                sms = vonage.Sms(client)

                # Use self.contact_list to get the related ContactList instance
                contact_obj = Contact.objects.filter(
                    contact_list=contact_list)
                try:
                    for recipient in contact_obj:
                        if content_link:
                            responseData = sms.send_message(
                                {
                                    "from": '+12012550867',
                                    "to": f'+{recipient.phone_number}',
                                    "text": sms_text.replace('#Link', content_link).replace('#FirstName', recipient.first_name) +
                                    "\n\n\n\n\n" +
                                    f'\nClick to Opt-out: {smsObj.unsubscribe_path}/{recipient.id}',
                                    "client-ref": unique_tracking_id
                                }
                            )
                        else:
                            responseData = sms.send_message(
                                {
                                    "from": "+12012550867",
                                    "to": f'+{recipient.phone_number}' +
                                    "\n\n\n\n\n" +
                                    f'\nClick to Opt-out: {smsObj.unsubscribe_path}/{recipient.id}',
                                    "text": sms_text.replace('#FirstName', recipient.first_name),
                                    "client-ref": unique_tracking_id
                                }
                            )

                    smsObj.sms_sends = contact_list.contact_lenght
                    smsObj.save()
                    message.status = 'sent'
                    message.save()
                    smsObj.is_sent = True
                    analytics_data.total_sends += contact_list.contact_lenght
                    analytics_data.save()
                    cache_key = f"messages:{smsObj.user.id}"
                    cache.delete(cache_key)
                    if responseData["messages"][0]["status"] == "0":
                        pass  # Moved this line inside the if block
                    else:
                        pass
                    from .views import schedule_archive_task
                    schedule_archive_task(smsObj.id, smsObj.scheduled_time)
                    print(
                        f"Message failed with error: {responseData['messages'][0]['error-text']}")

                except Exception as e:
                    print("Error sending SMS:", str(e))
                    send_email_notification(user.id)

            else:
                pass
    except Sms.DoesNotExist:
        pass


@shared_task
def send_sms(unique_tracking_id: None, user: None):
    try:
        from .models import Sms
        from base.models import ContactList, Message, Contact, CustomUser
        print(unique_tracking_id)
        smsObj = Sms.objects.get(unique_tracking_id=unique_tracking_id)
        print("SMS", smsObj)
        user = CustomUser.objects.get(id=smsObj.user.id)
        analytics_data = AnalyticsData.objects.get(custom_user=smsObj.user.id)
        contact_list = ContactList.objects.get(id=smsObj.contact_list.id)
        message = Message.objects.get(id=smsObj.message.id)
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
        button_count = 0

        with transaction.atomic():
            if not smsObj.is_sent:
                client = vonage.Client(
                    key=settings.VONAGE_ID, secret=settings.VONAGE_TOKEN)
                sms = vonage.Sms(client)

                # Use self.contact_list to get the related ContactList instance

                contact_obj = Contact.objects.filter(
                    contact_list=contact_list)
                # Get value for total sms sends based on contact list length

                for recipient in contact_obj:

                    if content_link:
                        responseData = sms.send_message(
                            {
                                "from": 'Nordiq Labs',
                                "to": f'+{recipient.phone_number}',
                                "text": sms_text.replace('#Link', content_link).replace('#FirstName', recipient.first_name) +
                                "\n\n\n\n\n" +
                                f'\nClick to Opt-out: {smsObj.unsubscribe_path}/{recipient.id}',
                                "client-ref": unique_tracking_id
                            }
                        )

                    else:

                        responseData = sms.send_message(
                            {
                                "from": "+Nordiq Labs",
                                "to": f'+{recipient.phone_number}',
                                "text": sms_text.replace('#FirstName', recipient.first_name) +
                                "\n\n\n\n\n" +
                                f'\nClick to Opt-out:{smsObj.unsubscribe_path}/{recipient.phone_number}',
                                "client-ref": unique_tracking_id
                            }
                        )
                smsObj.sms_sends = contact_list.contact_lenght
                smsObj.is_sent = True

                smsObj.save()
                message.status = 'sent'
                message.save()
                analytics_data.total_sends += contact_list.contact_lenght
                analytics_data.save()
                cache_key = f"messages:{smsObj.user.id}"
                cache.delete(cache_key)
            else:
                pass  # If is_sent is True, save the instance
    except Exception as e:
        send_email_notification(user.id)
        print(f'There has been an error {str(e)}')


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
    try:
        with transaction.atomic():
            sms = Sms.objects.get(id=sms_id)
            message = sms.message  # Assuming Sms has a ForeignKey to Message

            message.status = 'archived'
            message.save()

            custom_user = sms.user
            custom_user.archived_state = True
            custom_user.save()

            total_clicks = (
                sms.button_1 + sms.button_2 +
                sms.button_3 + sms.button_4 + sms.click_button + sms.click_number
            )
            audience = sms.sms_sends
            total_views = sms.total_views
            unsub_users = 1
            # Weights for performance calculation
            w1 = 0.4  # Weight for total views
            w2 = 0.6  # Weight for total clicks
            w3 = 0.1  # Weight for unsubscribes

            # Performance calculation based on the provided formula
            if audience > 0 and total_views > 0:
                overall_performance = (
                    (total_views / audience) * w1 +
                    (total_clicks / audience) * w2 -
                    (unsub_users / audience) * w3
                )
            else:
                # Set to 0 if audience or views are zero to avoid division by zero
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

            return 'Message archived and SMS deleted successfully'
    except Sms.DoesNotExist:
        return f'SMS with id {sms_id} does not exist'
    except Message.DoesNotExist:
        return f'Message related to SMS id {sms_id} does not exist'
    except Exception as e:
        # Log the exception details for debugging purposes
        return f'An error occurred: {str(e)}'
