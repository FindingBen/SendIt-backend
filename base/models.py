from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.apps import apps
from .utils.calculations import generate_hash


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
            package_plan = PackagePlan.objects.get(id=1)
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

    def serialize_package_plan(self):
        # Implement custom serialization logic here
        return {
            'package_plan': self.package_plan.plan_type,
            'sms_count': self.sms_count,
            # Add other relevant data
        }


class Message(models.Model):
    users = models.ForeignKey(User, on_delete=models.CASCADE)
    message_name = models.CharField(default='Content 1', max_length=20)
    created_at = models.DateField(
        auto_now_add=True)
    status = models.CharField(
        max_length=10, blank=True, null=True, default='Draft')


class Element(models.Model):

    element_type = models.CharField(max_length=20, null=True)
    message = models.ForeignKey(Message, on_delete=models.CASCADE)
    image = models.ImageField(blank=True, null=True)
    alignment = models.CharField(max_length=20, null=True)
    text = models.TextField(blank=True)
    button_title = models.CharField(max_length=20, null=True)
    button_link = models.CharField(max_length=100, null=True)
    button_color = models.CharField(max_length=20, default='#000000')
    order = models.PositiveIntegerField()


class ContactList(models.Model):
    users = models.ForeignKey(User, on_delete=models.CASCADE)
    list_name = models.CharField(max_length=20)
    contact_lenght = models.IntegerField(null=True, blank=True)

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


class Contact(models.Model):
    contact_list = models.ForeignKey(
        ContactList, null=True, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=20)
    last_name = models.CharField(max_length=20)
    phone_number = models.BigIntegerField()
    hashed_phone = models.CharField(default='TBA', max_length=200)
    email = models.EmailField()

    def save(self, *args, **kwargs):
        phone_to_hash = generate_hash(self.phone_number)
        self.hashed_phone = phone_to_hash

        super(Contact, self).save(*args, **kwargs)
