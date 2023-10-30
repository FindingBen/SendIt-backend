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
    unsubscribe_path = models.CharField(
        max_length=100, default='https://sendit-frontend-production.up.railway.app/unsubscribe')
    not_delivered = models.IntegerField(default=0)
    scheduled_time = models.DateTimeField(null=True, blank=True)
