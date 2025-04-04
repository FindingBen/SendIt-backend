from django.db import models
from base.models import ContactList, CustomUser, Message
from django.contrib.auth.models import User
import shortuuid
from django.db import transaction


class Sms(models.Model):
    unique_tracking_id = models.CharField(
        max_length=22,
        default=shortuuid.uuid,
        unique=True
        # Ensures the field is not editable in admin
    )
    created_at = models.DateField(auto_now_add=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    message = models.ForeignKey(Message, on_delete=models.CASCADE)
    sender = models.CharField(max_length=20, null=False)
    sms_text = models.TextField(max_length=500, null=False)
    content_link = models.URLField(max_length=500, null=True, blank=True)
    contact_list = models.ForeignKey(
        ContactList, on_delete=models.SET_NULL, null=True, blank=True)
    has_button = models.BooleanField(default=False)
    sms_sends = models.IntegerField(default=0)
    total_bounce_rate = models.DecimalField(
        max_digits=3, decimal_places=1, default=0)
    total_overall_rate = models.DecimalField(
        max_digits=3, decimal_places=1, default=0)
    total_views = models.IntegerField(default=0)
    button_1 = models.IntegerField(default=0)
    button_2 = models.IntegerField(default=0)
    button_3 = models.IntegerField(default=0)
    button_4 = models.IntegerField(default=0)
    button_1_name = models.CharField(null=True)
    button_2_name = models.CharField(null=True)
    button_3_name = models.CharField(null=True)
    button_4_name = models.CharField(null=True)
    click_number = models.IntegerField(default=0)
    click_button = models.IntegerField(default=0)
    is_sent = models.BooleanField(default=False)
    delivered = models.IntegerField(default=0)
    unsubscribe_path = models.CharField(
        max_length=100, default='https://sendit-frontend-production.up.railway.app/opt-out')
    not_delivered = models.IntegerField(default=0)
    scheduled_time = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.pk:

            self.unique_tracking_id = str(self.unique_tracking_id)[:7]
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


class CampaignStats(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.ForeignKey(Message, on_delete=models.CASCADE)
    engagement = models.IntegerField(default=0)
    name = models.CharField(null=True)
    total_clicks = models.IntegerField(default=0)
    audience = models.IntegerField(default=0)
    unsub_users = models.IntegerField(default=0)
    overall_perfromance = models.IntegerField(default=0)
    campaign_start = models.DateField(null=True)
    campaign_end = models.DateField(null=True)
