from __future__ import absolute_import, unicode_literals
from celery import shared_task
import vonage
import uuid
from django.db import transaction


@shared_task
def send_scheduled_sms(unique_tracking_id: uuid.UUID):

    try:
        from .models import Sms
        from base.models import CustomUser, ContactList, Message, Contact
        print('here', unique_tracking_id)
        smsObj = Sms.objects.get(unique_tracking_id=unique_tracking_id)
        custom_user = CustomUser.objects.get(id=smsObj.user.id)
        contact_list = ContactList.objects.get(id=smsObj.contact_list.id)
        message = Message.objects.get(id=smsObj.message.id)
        content_link = smsObj.content_link
        sms_text = smsObj.sms_text
        print("Sms", content_link)

        with transaction.atomic():
            if not smsObj.is_sent:

                client = vonage.Client(
                    key='33572b56', secret='cq75YEW2e1Z5coGZ')
                sms = vonage.Sms(client)

                # Use self.contact_list to get the related ContactList instance

                contact_obj = Contact.objects.filter(
                    contact_list=contact_list)
                # Get value for total sms sends based on contact list length

                numbers_dict = {
                    contact.first_name: contact.phone_number for contact in contact_obj
                }

                content_link = content_link + \
                    str(unique_tracking_id)
                try:
                    for recipient_number in numbers_dict.values():

                        if content_link:

                            responseData = sms.send_message(
                                {
                                    "from": '+12012550867',
                                    "to": f'+{recipient_number}',
                                    "text": sms_text.replace('#Link', content_link),
                                    "client-ref": unique_tracking_id
                                }
                            )

                        else:
                            responseData = sms.send_message(
                                {
                                    "from": "+12012550867",
                                    "to": f'+{recipient_number}',
                                    "text": sms_text,
                                    "client-ref": unique_tracking_id
                                }
                            )

                    smsObj.sms_sends = contact_list.contact_lenght
                    smsObj.save()
                    message.status = 'sent'
                    message.save()
                    smsObj.is_sent = True

                    if responseData["messages"][0]["status"] == "0":
                        pass  # Moved this line inside the if block

                    else:

                        print(
                            f"Message failed with error: {responseData['messages'][0]['error-text']}")

                except Exception as e:
                    print("Error sending SMS:", str(e))

            else:
                pass
        # You may want to use a third-party SMS gateway or library for this
        print('is it running?UPDATE')

    except Sms.DoesNotExist:
        pass


@shared_task
def send_sms(unique_tracking_id: uuid.UUID):
    print('Test')

    from .models import Sms
    from base.models import CustomUser, ContactList, Message, Contact
    print('uuid', unique_tracking_id)
    smsObj = Sms.objects.get(unique_tracking_id=unique_tracking_id)
    print(smsObj)
    contact_list = ContactList.objects.get(id=smsObj.contact_list.id)
    message = Message.objects.get(id=smsObj.message.id)
    content_link = smsObj.content_link
    sms_text = smsObj.sms_text
    print("sms sends", contact_list.contact_lenght)
    with transaction.atomic():
        if not smsObj.is_sent:
            print('sent?')
            client = vonage.Client(
                key='33572b56', secret='cq75YEW2e1Z5coGZ')
            sms = vonage.Sms(client)

            # Use self.contact_list to get the related ContactList instance

            contact_obj = Contact.objects.filter(
                contact_list=contact_list)
            # Get value for total sms sends based on contact list length

            numbers_dict = {
                contact.first_name: contact.phone_number for contact in contact_obj
            }

            content_link = content_link + \
                f'{unique_tracking_id}'
        try:

            for recipient_number in numbers_dict.values():

                if content_link:

                    responseData = sms.send_message(
                        {
                            "from": '+12012550867',
                            "to": f'+{recipient_number}',
                            "text": sms_text.replace('#Link', content_link),
                            "client-ref": unique_tracking_id
                        }
                    )

                else:
                    responseData = sms.send_message(
                        {
                            "from": "+12012550867",
                            "to": f'+{recipient_number}',
                            "text": sms_text,
                            "client-ref": unique_tracking_id
                        }
                    )

            smsObj.sms_sends = contact_list.contact_lenght
            smsObj.save()
            smsObj.is_sent = True
            message.status = 'sent'
            message.status = 'sent'
            message.save()

            if responseData["messages"][0]["status"] == "0":

                print('done')
            else:

                print(
                    f"Message failed with error: {responseData['messages'][0]['error-text']}")

        except:
            pass

        else:
            pass  # If is_sent is True, save the instance
