from django.db import models
from base.models import ContactList, CustomUser
from twilio.rest import Client


class Sms(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    # message = models.ForeignKey(Message, on_delete=models.CASCADE)
    sender = models.CharField(max_length=20, null=False)
    sms_text = models.TextField(max_length=100, null=False)
    content_link = models.URLField(max_length=100, null=True, blank=True)

    def save(self, *args, **kwargs):
        account_sid = 'AC60677c3a06dcd08999640a1db5b03770'
        auth_token = 'f52f0d2086c6ac336c994c4218858ab8'
        client = Client(account_sid, auth_token)

        NUMBERS = {

            'Ben': '+4552529924'
        }

        # Get a list of all the phone numbers from the NUMBERS dictionary
        recipient_numbers = NUMBERS.values()

        for recipient_number in recipient_numbers:

            if self.content_link:
                sms = client.messages.create(
                    from_='+14847299112',
                    body=self.sms_text.replace('#Link', self.content_link),
                    to=recipient_number
                )
            else:
                sms = client.messages.create(
                    from_='+14847299112',
                    body=self.sms_text,
                    to=recipient_number
                )

        return super().save(*args, **kwargs)
