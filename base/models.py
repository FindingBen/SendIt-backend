from django.db import models
from django.contrib.auth.models import User


class Message(models.Model):
    users = models.ForeignKey(User, on_delete=models.CASCADE)

    element_list = models.ManyToManyField('Element', related_name='messages')
# text = models.TextField(null=True)
# image = models.ImageField(null=True)


class Element(models.Model):
    # Define fields common to all element types
    # For example, you can have a type field to distinguish between different element types
    element_type = models.CharField(max_length=20, null=True)
    # Add other fields specific to each element type
    # For example, for image element, you can have an image field
    image = models.ImageField(blank=True, null=True)
    alignment = models.CharField(max_length=20, null=True)
    # For text element, you can have a text field
    text = models.TextField(blank=True)
    button_title = models.CharField(max_length=20, null=True)
    button_link = models.CharField(max_length=100, null=True)


class ContactList(models.Model):
    users = models.ForeignKey(User, on_delete=models.CASCADE)
    list_name = models.CharField(max_length=20)


class Contact(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    contact_list = models.ForeignKey(
        ContactList, null=True, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=20)
    last_name = models.CharField(max_length=20)
    phone_number = models.IntegerField()
    email = models.EmailField()
