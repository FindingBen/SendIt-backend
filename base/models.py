from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.apps import apps
from uuid import uuid4
from django.utils import timezone
from django.conf import settings


class PackagePlan(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, blank=True, null=True)
    plan_type = models.CharField(max_length=20)
    price = models.IntegerField()
    sms_count_pack = models.IntegerField()
    offer1 = models.CharField(max_length=200, null=True, blank=True)
    offer2 = models.CharField(max_length=200, null=True, blank=True)
    offer3 = models.CharField(max_length=200, null=True, blank=True)
    offer4 = models.CharField(max_length=200, null=True, blank=True)
    offer5 = models.CharField(max_length=200, null=True, blank=True)
    offer6 = models.CharField(max_length=200, null=True, blank=True)
    offer7 = models.CharField(max_length=200, null=True, blank=True)
    offer8 = models.CharField(max_length=200, null=True, blank=True)


class CustomUser(User):
    USER_TYPE_CHOICES = [
        ('Independent', 'Independent'),
        ('Business', 'Business'),
        ('Other', 'Other'),
    ]

    package_plan = models.ForeignKey(
        PackagePlan, on_delete=models.CASCADE, blank=True, null=True)
    sms_count = models.IntegerField(default=0)
    user_type = models.CharField(
        max_length=20, choices=USER_TYPE_CHOICES)
    custom_email = models.EmailField(unique=True)
    last_password_change = models.DateField(null=True, blank=True)
    archived_state = models.BooleanField(default=False)
    welcome_mail_sent = models.BooleanField(default=False)
    stripe_custom_id = models.CharField(default=None, null=True)
    scheduled_subscription = models.DateField(null=True, blank=True)
    scheduled_package = models.CharField(default=None, null=True)
    shopify_connect = models.BooleanField(default=False)

    def serialize_package_plan(self):
        # Implement custom serialization logic here
        if self.package_plan:
            if self.package_plan.plan_type == settings.TRIAL_PLAN:
                list_limit = 2
                recipients_limit = 100
            elif self.package_plan.plan_type == settings.BASIC_PLAN:
                list_limit = 3
                recipients_limit = 5000
            elif self.package_plan.plan_type == settings.SILVER_PLAN:
                list_limit = 10
                recipients_limit = 10000
            elif self.package_plan.plan_type == settings.GOLD_PLAN:
                list_limit = 20
                recipients_limit = "Unlimited"
            # elif self.package_plan.plan_type == "Demo package":
            #     list_limit = 5
            #     recipients_limit = 2000
            return {
                'package_plan': self.package_plan.plan_type,
                'sms_count': self.sms_count,
                'list_limit': list_limit,
                'recipients_limit': recipients_limit,
                # Add other relevant data if needed
            }
        else:
            # Return default values if no package is set
            return {
                'package_plan': 'No package',
                'sms_count': self.sms_count,
                'list_limit': 0,
                'recipients_limit': 0,
            }


class ShopifyStore(models.Model):
    email = models.EmailField(null=True)
    first_name = models.CharField(max_length=255, null=True)
    last_name = models.CharField(max_length=255, null=True)
    shop_domain = models.CharField(max_length=255, unique=True)
    access_token = models.CharField(max_length=255)


class EmailConfirmationToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)


class Message(models.Model):

    CAMPAIGN_TYPE = [
        ('Promotional', 'Promotional'),
        ('Notification', 'Notification')
    ]

    SMS_SEND = [
        ('Send', 'Send'),
        ('Schedule', 'Schedule')
    ]

    users = models.ForeignKey(User, on_delete=models.CASCADE)
    message_name = models.CharField(max_length=40)
    created_at = models.DateField(
        auto_now_add=True)
    status = models.CharField(
        max_length=10, blank=True, null=True, default='Draft')
    total_overall_progress = models.IntegerField(default=0)
    recipient_list = models.CharField(max_length=400, null=True)
    campaign_type = models.CharField(
        max_length=25, choices=CAMPAIGN_TYPE, null=True)
    sms_text = models.TextField(max_length=150, null=True)
    sms_send = models.CharField(max_length=20, choices=SMS_SEND, null=True)


class SurveyResponse(models.Model):
    element = models.ForeignKey('Element', on_delete=models.CASCADE)
    survey_type = models.CharField(max_length=20, null=True)
    like_response = models.IntegerField(null=True, default=0)
    dislike_response = models.IntegerField(null=True, default=0)
    numeric_response = models.IntegerField(null=True, default=0)


class Element(models.Model):

    SURVEY_CHOICES = [
        ('Like/Dislike', 'Like/Dislike'),
        ('Question Survey', 'Question Survey'),
    ]
    unique_button_id = models.CharField(default=None, null=True)
    element_type = models.CharField(max_length=20, null=True)
    message = models.ForeignKey(Message, on_delete=models.CASCADE)
    image = models.ImageField(blank=True, null=True)
    alignment = models.CharField(max_length=20, null=True)
    text = models.TextField(blank=True)
    survey = models.CharField(max_length=50, null=True)
    question_type = models.CharField(
        max_length=20, choices=SURVEY_CHOICES, null=True)
    button_title = models.CharField(max_length=20, null=True)
    button_link = models.CharField(max_length=100, null=True)
    button_link_track = models.CharField(max_length=100, null=True)
    button_color = models.CharField(max_length=20, default='#000000')
    order = models.PositiveIntegerField()

    def save_response(self, like_response=None, dislike_response=None, numeric_response=None):
        if self.element_type == 'Survey':
            survey_response = SurveyResponse(
                element=self,
                # Add other fields as needed
            )
            survey_response.save()


class CarouselImage(models.Model):
    element = models.ForeignKey(
        'Element', related_name='carousel_images', on_delete=models.CASCADE)
    image = models.ImageField(blank=True, null=True)
    image_src = models.URLField(max_length=300, null=True, blank=True)
    external_url = models.URLField(blank=True, null=True)


class ContactList(models.Model):
    unique_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    users = models.ForeignKey(User, on_delete=models.CASCADE)
    list_name = models.CharField(max_length=50)
    shopify_list = models.BooleanField(default=False)
    contact_lenght = models.IntegerField(null=True, blank=True)
    created_at = models.DateField(
        auto_now_add=True)

    @receiver(post_save, sender='base.Contact')
    @receiver(post_delete, sender='base.Contact')
    def update_contact_list_count(sender, instance, **kwargs):
        # Replace 'yourappname' with your actual app name
        Contact = apps.get_model('base', 'Contact')

        contact_list = instance.contact_list

        contact_count = Contact.objects.filter(
            contact_list=contact_list).count()
        contact_list.contact_lenght = contact_count
        contact_list.save()

    @classmethod
    def update_contact_count(cls, contact_list):
        from .models import Contact  # avoid circular import
        count = Contact.objects.filter(contact_list=contact_list).count()
        contact_list.contact_lenght = count
        contact_list.save()

    def save(self, *args, **kwargs):
        if not self.created_at:
            self.created_at = timezone.now().date()
        super().save(*args, **kwargs)


class Contact(models.Model):
    users = models.ForeignKey(User, null=True, on_delete=models.CASCADE)
    custom_id = models.CharField(max_length=100, null=True, blank=True)
    contact_list = models.ForeignKey(
        ContactList, null=True, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=20, blank=True, null=True)
    last_name = models.CharField(max_length=20, blank=True, null=True)
    phone_number = models.CharField(blank=True, null=True)
    is_shopify_contact = models.BooleanField(default=False)
    email = models.EmailField(blank=True, null=True)
    allowed = models.BooleanField(default=True)
    created_at = models.DateField(
        auto_now_add=True)


class AnalyticsData(models.Model):
    custom_user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    total_sends = models.IntegerField(default=0)
    total_views = models.IntegerField(default=0)
    total_clicks = models.IntegerField(default=0)
    total_bounces = models.IntegerField(default=0)
    total_bounce_rate = models.IntegerField(default=0)
    total_overall_rate = models.IntegerField(default=0)
    total_spend = models.IntegerField(default=0)
    last_updated = models.DateField(auto_now_add=True)
    total_delivered = models.IntegerField(default=0)
    total_not_delivered = models.IntegerField(default=0)
    tota_unsubscribed = models.IntegerField(default=0)
    tota_subscribed = models.IntegerField(default=0)
    contacts_limit_reached = models.BooleanField(default=False)
    contact_list_limit_reached = models.BooleanField(default=False)

    def calculate_performance(self):
        # Ensure we don't divide by zero
        if self.total_sends == 0:
            return 0  # No messages sent, so no performance to calculate

        # Calculate Click-Through Rate (CTR)
        ctr = (self.total_clicks / self.total_sends) * \
            100 if self.total_clicks > 0 else 0

        # Calculate View Rate
        view_rate = (self.total_views / self.total_sends) * \
            100 if self.total_views > 0 else 0

        # Calculate Cost per Click (CPC) and Cost per View (CPV)
        cpc = self.total_spend / self.total_clicks if self.total_clicks > 0 else 0
        cpv = self.total_spend / self.total_views if self.total_views > 0 else 0

        # Define weight factors for each component (these can be adjusted based on preference)
        ctr_weight = 0.4
        view_rate_weight = 0.4
        cost_efficiency_weight = 0.2

        # Cost efficiency: You might want to penalize higher costs, so we inverse them
        # Normalize by multiplying with 100 to balance with other factors
        cost_efficiency = (1 / cpc * 100 if cpc > 0 else 0) + \
            (1 / cpv * 100 if cpv > 0 else 0)

        # Calculate overall performance as a weighted sum
        overall_performance = (
            (ctr * ctr_weight) +
            (view_rate * view_rate_weight) +
            (cost_efficiency * cost_efficiency_weight)
        ) / self.total_sends

        # Update the total overall rate and save
        self.total_overall_rate = round(overall_performance, 2)
        self.save()

        return self.total_overall_rate


class QRCode(models.Model):
    contact_list = models.ForeignKey('ContactList', on_delete=models.CASCADE)
    qr_image = models.ImageField(blank=True, null=True)
    qr_data = models.CharField(default=None)
