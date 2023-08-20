from django.db import models
from base.models import ContactList, CustomUser, Message, Contact
from twilio.rest import Client
import vonage
import os


class Sms(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    message = models.ForeignKey(Message, on_delete=models.CASCADE)
    sender = models.CharField(max_length=20, null=False)
    sms_text = models.TextField(max_length=100, null=False)
    content_link = models.URLField(max_length=100, null=True, blank=True)
    contact_list = models.ForeignKey(ContactList, on_delete=models.CASCADE)

    def save(self, *args, **kwargs):
        # account_sid = 'AC5ce864bd776a0057c559f1f7d98aa910'
        # auth_token = '400acc1a2488f9a1fa8c88d6bc46b54b'
        # client = Client(account_sid, auth_token)
        client = vonage.Client(key="111", secret="111")
        sms = vonage.Sms(client)

        # Use self.contact_list to get the related ContactList instance
        contact_list_obj = self.contact_list
        contact_obj = Contact.objects.filter(contact_list=contact_list_obj)

        numbers_dict = {
            contact.first_name: contact.phone_number for contact in contact_obj
        }

        print(numbers_dict)
        NUMBERS = {

            'Ben': '+4552529924',
            'Patjo': '+4552737611'
        }

        try:
            for recipient_number in NUMBERS.values():
                if self.content_link:

                    responseData = sms.send_message(
                        {
                            "from": "Vonage APIs",
                            "to": recipient_number,
                            "text": self.sms_text.replace('#Link', self.content_link),
                        }
                    )
                else:
                    responseData = sms.send_message(
                        {
                            "from": "Vonage APIs",
                            "to": "4552529924",
                            "text": self.sms_text,
                        }
                    )

            if responseData["messages"][0]["status"] == "0":
                print("Message sent successfully.")
            else:
                print(
                    f"Message failed with error: {responseData['messages'][0]['error-text']}")
        except Exception as e:
            print("Error sending SMS:", str(e))
        # print("Self.message before saving SMS:", self.message.status)
        # try:
        #     # Send the SMS
        #     for recipient_number in NUMBERS.values():
        #         if self.content_link:
        #             sms = client.messages.create(
        #                 from_='+15735945164',
        #                 body=self.sms_text.replace('#Link', self.content_link),
        #                 to=recipient_number
        #             )
        #         else:
        #             sms = client.messages.create(
        #                 from_='+15735945164',
        #                 body=self.sms_text,
        #                 to=recipient_number
        #             )
        # except Exception as e:
        #     # Handle exceptions (e.g., Twilio API errors) here
        #     print("Error sending SMS:", str(e))
        # # If SMS sent successfully, update the Message status to 'sent'
        # self.message.status = 'sent'

        # self.message.save()

        return super().save(*args, **kwargs)
