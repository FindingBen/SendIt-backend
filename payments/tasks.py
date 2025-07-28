import logging
from django.utils import timezone
from django.conf import settings
from base.models import CustomUser, PackagePlan, AnalyticsData, ShopifyStore
from celery import shared_task
from base.shopify_functions import ShopifyFactoryFunction
from notification.models import Notification
from .models import Billing
from datetime import datetime, date
from django.db import transaction, IntegrityError
from base.email.email import send_plan_renewal_email

logger = logging.getLogger(__name__)


@shared_task
def activate_scheduled_packages():
    today = timezone.now().date()
    users = CustomUser.objects.filter(scheduled_subscription=today)

    for user in users:
        shopify_store = ShopifyStore.objects.get(
            custom_email=user.custom_email)
        shopify_domain = shopify_store.shop_domain
        token = shopify_store.access_token
        url = f"https://{shopify_domain}/admin/api/{settings.SHOPIFY_API_VERSION}/graphql.json"

        shopify_factory = ShopifyFactoryFunction(
            shopify_domain, token, url, query=None
        )
        response = shopify_factory.get_users_charge()
        data = response.json()

        # Check current active subscription
        current_subs = data.get("data", {}).get(
            "currentAppInstallation", {}).get("activeSubscriptions", [])

        if len(current_subs) == 0:
            continue
        latest_plan = current_subs[0]
        plan_name = latest_plan.get("name")
        plan_status = latest_plan.get("status")
        next_billing_date_str = latest_plan.get(
            'currentPeriodEnd')  # ISO 8601 format
        next_billing_date = datetime.fromisoformat(
            next_billing_date_str.replace('Z', '+00:00')).date()
        shopify_charge_id = latest_plan.get("id").split('/')[-1]

        # Validate subscription is ACTIVE
        if plan_status != "ACTIVE":
            continue
        package_obj = PackagePlan.objects.filter(plan_type=plan_name).first()
        if not package_obj:
            continue

        with transaction.atomic():
            Billing.objects.create(
                user=user,
                billing_amount=package_obj.price,
                billing_plan=package_obj.plan_type,
                billing_status=plan_status,
                shopify_charge_id=shopify_charge_id
            )
            logger.info('Activating plan for user:', user.email)
            user.package_plan = package_obj
            user.sms_count = package_obj.sms_count_pack
            user.scheduled_subscription = next_billing_date
            user.save()

            analytics = AnalyticsData.objects.get(custom_user=user.id)
            analytics.total_spend += package_obj.price
            analytics.save()
            logger.info('DONE', next_billing_date)
            send_plan_renewal_email(user.id, package_obj)

            Notification.objects.create(
                user=user,
                title=f"{package_obj.plan_type} Activated",
                message=f"Your plan '{package_obj.plan_type}' has been activated successfully.",
                notif_type="success"
            )
    logger.info(f"Activated {users.count()} scheduled packages.")
    return f"Activated {users.count()} scheduled plans"
