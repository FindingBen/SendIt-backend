from django.db import models
from base.models import ContactList, CustomUser, Message, Contact
import vonage
import shortuuid
import uuid
from django.db import transaction
from django.conf import settings


class Sms(models.Model):
    unique_tracking_id = models.CharField(
        max_length=22,
        default=shortuuid.uuid,
        unique=True,
        editable=False  # Ensures the field is not editable in admin
    )
    created_at = models.DateField(auto_now_add=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    message = models.ForeignKey(Message, on_delete=models.CASCADE)
    sender = models.CharField(max_length=20, null=False)
    sms_text = models.TextField(max_length=500, null=False)
    content_link = models.URLField(max_length=500, null=True, blank=True)
    contact_list = models.ForeignKey(ContactList, on_delete=models.CASCADE)
    sms_sends = models.IntegerField(default=0)
    total_bounce_rate = models.DecimalField(
        max_digits=3, decimal_places=1, default=0)
    total_overall_rate = models.DecimalField(
        max_digits=3, decimal_places=1, default=0)
    total_views = models.IntegerField(default=0)
    click_number = models.IntegerField(default=0)
    is_sent = models.BooleanField(default=False)
    delivered = models.IntegerField(default=0)
    unsubscribe_path = models.CharField(
        max_length=100, default='https://sendit-frontend-production.up.railway.app/opt-out')
    not_delivered = models.IntegerField(default=0)
    scheduled_time = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.pk:
            print('wokring?', self)
            self.unique_tracking_id = str(self.unique_tracking_id)[:7]
            self.created_at = self.created_at.strftime('%Y-%m-%d')
            print('S')
        super().save(*args, **kwargs)

    @classmethod
    def update_from_values(cls, values, record_id):
        try:
            with transaction.atomic():
                sms_model = cls.objects.get(message_id=record_id)
                sms_model.total_bounce_rate = round(
                    values['sorted_total_data']['bounceRate'], 1)
                sms_model.total_overall_rate = round(values['overall_perf'], 1)
                sms_model.total_views = values['sorted_total_data']['screen_views_total']
                sms_model.save()
        except cls.DoesNotExist:
            # Handle the case when the Sms object with the given message_id is not found
            pass
        except Exception as e:
            # Handle other exceptions that might occur during the update
            print(f"An error occurred: {e}")
