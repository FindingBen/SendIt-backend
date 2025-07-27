import logging
from django.utils import timezone
from base.models import CustomUser, PackagePlan, AnalyticsData
from celery import shared_task
logger = logging.getLogger(__name__)


@shared_task
def activate_scheduled_packages():
    today = timezone.now().date()
    users = CustomUser.objects.filter(scheduled_subscription=today)

    for user in users:
        # Default plan or any logic to get the new plan
        new_plan = PackagePlan.objects.get(plan_type=user.scheduled_package)
        logger.info(f"Activating plan for {user.email}")
        user.package_plan = new_plan
        user.sms_count = new_plan.sms_count_pack

        user.save()
        analytics = AnalyticsData.objects.get(custom_user=user.id)
        analytics.total_spend += new_plan.price

    logger.info(f"Activated {users.count()} scheduled packages.")
    return f"Activated {users.count()} scheduled plans"
