from __future__ import absolute_import, unicode_literals
from celery import shared_task
import vonage
from django.conf import settings
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
                    cache_key = f"messages:{smsObj.user.id}"
                    cache.delete(cache_key)
                    if responseData["messages"][0]["status"] == "0":
                        pass  # Moved this line inside the if block

                    else:

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

        smsObj = Sms.objects.get(unique_tracking_id=unique_tracking_id)
        user = CustomUser.objects.get(id=smsObj.user.id)
        contact_list = ContactList.objects.get(id=smsObj.contact_list.id)
        message = Message.objects.get(id=smsObj.message.id)
        content_link = smsObj.content_link
        sms_text = smsObj.sms_text

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
                                "from": 'spplane',
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
                cache_key = f"messages:{smsObj.user.id}"
                cache.delete(cache_key)
            else:
                pass  # If is_sent is True, save the instance
    except Exception as e:
        send_email_notification(user.id)
        print(str(e))


def generate_hash(phone_number):
    # Create a hashlib object
    sha256 = hashlib.sha256()
    # Update the hash object with the phone number as bytes
    sha256.update(str(phone_number).encode('utf-8'))

    # Get the hexadecimal representation of the hash
    hashed_phone = sha256.hexdigest()

    return hashed_phone
