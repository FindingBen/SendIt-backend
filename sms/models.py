from django.db import models
from base.models import ContactList, CustomUser, Message, Contact
import vonage
import uuid
from django.db import transaction
from django.conf import settings


class Sms(models.Model):
    unique_tracking_id = models.UUIDField(default=uuid.uuid4, unique=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    message = models.ForeignKey(Message, on_delete=models.CASCADE)
    sender = models.CharField(max_length=20, null=False)
    sms_text = models.TextField(max_length=500, null=False)
    content_link = models.URLField(max_length=500, null=True, blank=True)
    contact_list = models.ForeignKey(ContactList, on_delete=models.CASCADE)
    sms_sends = models.IntegerField(default=0)
    click_number = models.IntegerField(default=0)
    is_sent = models.BooleanField(default=False)
    delivered = models.IntegerField(default=0)
    scheduled = models.BooleanField(default=False)
    not_delivered = models.IntegerField(default=0)
    scheduled_time = models.DateTimeField(null=True, blank=True)

    # def save(self, *args, **kwargs):
    #     with transaction.atomic():
    #         if not self.is_sent:
    #             print("TEST TIME SCHEDULE::", self.scheduled_time)
    #             client = vonage.Client(
    #                 key='33572b56', secret='cq75YEW2e1Z5coGZ')
    #             sms = vonage.Sms(client)
    #             print(self.contact_list)
    #             # Use self.contact_list to get the related ContactList instance
    #             contact_list_obj = self.contact_list
    #             contact_obj = Contact.objects.filter(
    #                 contact_list=contact_list_obj)
    #             # Get value for total sms sends based on contact list length
    #             self.sms_sends = contact_list_obj.contact_lenght
    #             numbers_dict = {
    #                 contact.first_name: contact.phone_number for contact in contact_obj
    #             }

    #             self.content_link = self.content_link + \
    #                 f'{self.unique_tracking_id}'
    #             try:
    #                 for recipient_number in numbers_dict.values():

    #                     if self.content_link:

    #                         responseData = sms.send_message(
    #                             {
    #                                 "from": '+12012550867',
    #                                 "to": f'+{recipient_number}',
    #                                 "text": self.sms_text.replace('#Link', self.content_link),
    #                                 "client-ref": self.unique_tracking_id
    #                             }
    #                         )

    #                     else:
    #                         responseData = sms.send_message(
    #                             {
    #                                 "from": "+12012550867",
    #                                 "to": f'+{recipient_number}',
    #                                 "text": self.sms_text,
    #                                 "client-ref": self.unique_tracking_id
    #                             }
    #                         )

    #                 if responseData["messages"][0]["status"] == "0":
    #                     print(responseData)
    #                     self.message.status = 'sent'
    #                     self.message.save()
    #                     self.is_sent = True  # Moved this line inside the if block
    #                     super().save(*args, **kwargs)  # Save the instance here

    #                 else:

    #                     print(
    #                         f"Message failed with error: {responseData['messages'][0]['error-text']}")

    #             except Exception as e:
    #                 print("Error sending SMS:", str(e))
    #             else:
    #                 self.message.status = 'scheduled'
    #                 self.message.save()
    #                 super().save(*args, **kwargs)
    #                 print('Saved SMS but its not yet sent!')
    #         else:
    #             super().save(*args, **kwargs)  # If is_sent is True, save the instance
