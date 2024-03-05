from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser, AnalyticsData


@receiver(post_save, sender=CustomUser)
def create_analytics_data(sender, instance, created, **kwargs):
    if created:
        AnalyticsData.objects.create(custom_user=instance)
