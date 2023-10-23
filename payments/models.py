from django.db import models

from base.models import CustomUser
from django.dispatch import receiver
from django.db.models.signals import post_save


class UserPayment(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    payment_bool = models.BooleanField(default=False)
    stripe_checkout_id = models.CharField(max_length=500)


class Purchase(models.Model):
    userPayment = models.ForeignKey(UserPayment, on_delete=models.CASCADE)
    package_name = models.CharField(max_length=20)
    price = models.IntegerField(default=0)
    payment_method = models.CharField(max_length=20)
    payment_id = models.CharField(max_length=300)


@receiver(post_save, sender=CustomUser)
def create_user_payment(sender, instance, created, **kwargs):
    if created:
        UserPayment.objects.create(user=instance)
