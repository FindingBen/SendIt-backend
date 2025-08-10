from django.db import models

from base.models import CustomUser
from django.dispatch import receiver
from django.db.models.signals import post_save


class UserPayment(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    payment_bool = models.BooleanField(default=False)
    stripe_checkout_id = models.CharField(max_length=500)
    last_stripe_session_id = models.CharField(max_length=500,
                                              blank=True,
                                              null=True,
                                              default=None)
    purchase_id = models.CharField(max_length=250)


class Billing(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    billing_plan = models.CharField(max_length=50, default='Trial')
    billing_date = models.DateField(auto_now_add=True)
    billing_amount = models.IntegerField(default=0)
    billing_status = models.CharField(max_length=20, default='pending')
    shopify_charge_id = models.CharField(max_length=500, blank=True, null=True)


class Purchase(models.Model):
    userPayment = models.ForeignKey(UserPayment, on_delete=models.CASCADE)
    package_name = models.CharField(max_length=20)
    price = models.IntegerField(default=0)
    payment_method = models.CharField(max_length=20)
    payment_id = models.CharField(max_length=300)
    created_at = models.DateField(auto_now_add=True)


class StripeEvent(models.Model):
    event_id = models.CharField(max_length=255, unique=True)
    processed_at = models.DateTimeField(auto_now_add=True)


@receiver(post_save, sender=CustomUser)
def create_user_payment(sender, instance, created, **kwargs):
    if created:
        UserPayment.objects.create(user=instance)
