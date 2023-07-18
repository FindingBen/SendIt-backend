from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.base_user import AbstractBaseUser
from django.dispatch import receiver
from django.urls import reverse
from django_rest_passwordreset.signals import reset_password_token_created
from django.core.mail import send_mail


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
    package_plan = models.ForeignKey(
        PackagePlan, on_delete=models.CASCADE, blank=True, null=True)
    sms_count = models.IntegerField()

    def save(self, *args, **kwargs):
        if not self.pk:
            package_plan = PackagePlan.objects.get(id=4)
            self.package_plan = package_plan
            self.sms_count = 2

        is_new_instance = not self.pk
        original_instance = None

        if not is_new_instance:
            original_instance = CustomUser.objects.get(pk=self.pk)

        # Check if the package_plan value has changed
        if original_instance and original_instance.package_plan != self.package_plan:

            package_plan = PackagePlan.objects.get(id=self.package_plan.id)

            self.sms_count = package_plan.sms_count_pack
        super().save(*args, **kwargs)


class Message(models.Model):
    users = models.ForeignKey(User, on_delete=models.CASCADE)
    element_list = models.ManyToManyField('Element', related_name='messages')
    created_at = models.DateTimeField(auto_now_add=True)


class Element(models.Model):

    element_type = models.CharField(max_length=20, null=True)

    image = models.ImageField(blank=True, null=True)
    alignment = models.CharField(max_length=20, null=True)

    text = models.TextField(blank=True)
    button_title = models.CharField(max_length=20, null=True)
    button_link = models.CharField(max_length=100, null=True)


class ContactList(models.Model):
    users = models.ForeignKey(User, on_delete=models.CASCADE)
    list_name = models.CharField(max_length=20)


class Contact(models.Model):
    contact_list = models.ForeignKey(
        ContactList, null=True, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=20)
    last_name = models.CharField(max_length=20)
    phone_number = models.IntegerField()
    email = models.EmailField()
