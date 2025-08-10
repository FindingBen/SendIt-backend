from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'payments'

    def ready(self):
        from django_celery_beat.models import PeriodicTask, IntervalSchedule
        from django.utils.timezone import now
        import json

        schedule, _ = IntervalSchedule.objects.get_or_create(
            every=1,
            period=IntervalSchedule.DAYS,
        )

        PeriodicTask.objects.update_or_create(
            name='Activate Scheduled Packages for Stripe Users',
            defaults={
                'interval': schedule,
                'task': 'payments.tasks.activate_scheduled_packages_from_stripe',
                'start_time': now(),
                'enabled': True,
                'kwargs': json.dumps({})
            }
        )

        PeriodicTask.objects.update_or_create(
            name='Activate Subscription cancel for Stripe Users',
            defaults={
                'interval': schedule,
                'task': 'payments.tasks.cancel_subscription_monitor',
                'start_time': now(),
                'enabled': True,
                'kwargs': json.dumps({})
            }
        )

        PeriodicTask.objects.update_or_create(
            name='Activate Scheduled Packages',
            defaults={
                'interval': schedule,
                'task': 'payments.tasks.activate_scheduled_packages',
                'start_time': now(),
                'enabled': True,
                'kwargs': json.dumps({})
            }
        )
