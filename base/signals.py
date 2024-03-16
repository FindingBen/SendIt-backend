from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser, AnalyticsData, PackagePlan


@receiver(post_save, sender=CustomUser)
def create_analytics_data(sender, instance, created, **kwargs):
    if created:
        AnalyticsData.objects.create(custom_user=instance)


@receiver(post_save, sender=CustomUser)
def assign_package(sender, instance, created, **kwargs):
    if created:
        package_plan = PackagePlan.objects.get(id=1)
        user_instance = instance
        user_instance.package_plan = package_plan
        user_instance.sms_count += package_plan.sms_count_pack
        user_instance.save()
