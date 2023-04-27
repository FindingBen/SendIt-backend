from django.db import models
from django.contrib.auth.models import User


class Note(models.Model):
    users = models.ForeignKey(User, on_delete=models.CASCADE)
    body = models.TextField()


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