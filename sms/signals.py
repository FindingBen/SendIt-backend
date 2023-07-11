from django.db.models.signals import post_save
from django.dispatch import receiver
from base.models import CustomUser
from .models import Sms


@receiver(post_save, sender=Sms)
def update_user_field(sender, instance, created, **kwargs):
    if created:
        # Get the user related to OtherModel
        user = CustomUser.objects.get(id=instance.user_id)
        # Update the user's field with the desired value
        user.sms_count = user.sms_count - 1
        user.save()
