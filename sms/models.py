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
        client = vonage.Client(key='33572b56', secret='cq75YEW2e1Z5coGZ')
        sms = vonage.Sms(client)

        # Use self.contact_list to get the related ContactList instance
        contact_list_obj = self.contact_list
        contact_obj = Contact.objects.filter(contact_list=contact_list_obj)

        numbers_dict = {
            contact.first_name: contact.phone_number for contact in contact_obj
        }

        try:
            for recipient_number in numbers_dict.values():
                print(recipient_number)
                if self.content_link:

                    responseData = sms.send_message(
                        {
                            "from": '+12012550867',
                            "to": f'+{recipient_number}',
                            "text": self.sms_text.replace('#Link', self.content_link),
                        }
                    )
                    print('DATA', responseData)
                else:
                    responseData = sms.send_message(
                        {
                            "from": "+12012550867",
                            "to": f'+{recipient_number}',
                            "text": self.sms_text,
                        }
                    )

            if responseData["messages"][0]["status"] == "0":
                print("Message sent successfully.")

                self.message.status = 'sent'

                self.message.save()
            else:
                print(
                    f"Message failed with error: {responseData['messages'][0]['error-text']}")
        except Exception as e:
            print("Error sending SMS:", str(e))

        return super().save(*args, **kwargs)
