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

    def serialize_package_plan(self):
        # Implement custom serialization logic here
        return {
            'package_plan': self.package_plan.plan_type,
            'sms_count': self.sms_count,
            # Add other relevant data
        }


class EmailConfirmationToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)


class Message(models.Model):
    users = models.ForeignKey(User, on_delete=models.CASCADE)
    message_name = models.CharField(max_length=40)
    created_at = models.DateField(
        auto_now_add=True)
    status = models.CharField(
        max_length=10, blank=True, null=True, default='Draft')
    total_overall_progress = models.IntegerField(default=0)


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


class ContactList(models.Model):
    users = models.ForeignKey(User, on_delete=models.CASCADE)
    list_name = models.CharField(max_length=20)
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

    def save(self, *args, **kwargs):
        if not self.created_at:
            self.created_at = timezone.now().date()
        super().save(*args, **kwargs)


class Contact(models.Model):
    users = models.ForeignKey(User, null=True, on_delete=models.CASCADE)
    contact_list = models.ForeignKey(
        ContactList, null=True, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=20, blank=True, null=True)
    last_name = models.CharField(max_length=20, blank=True, null=True)
    phone_number = models.BigIntegerField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    created_at = models.DateField(
        auto_now_add=True)


class AnalyticsData(models.Model):
    custom_user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    total_sends = models.IntegerField(default=0)
    total_views = models.IntegerField(default=0)
    total_bounce_rate = models.IntegerField(default=0)
    total_overall_rate = models.IntegerField(default=0)
    last_updated = models.DateField(auto_now_add=True)
