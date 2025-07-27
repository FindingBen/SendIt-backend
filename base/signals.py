from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser, AnalyticsData, PackagePlan, QRCode, ContactList
from django.utils.timezone import now
from django_rest_passwordreset.signals import post_password_reset


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
        print("AAAAAAAAAAAAAAAAAAA")
        user_instance.save()


@receiver(post_password_reset)
def update_password_change_timestamp(sender, user, request, **kwargs):
    user.last_password_change = now()
    print('AAA')
    user.save(update_fields=['last_password_change'])


@receiver(post_save, sender=ContactList)
def create_qrcode(sender, instance, created, **kwargs):
    if created:  # Only run if a new ContactList is created
        import qrcode
        from io import BytesIO
        from django.core.files.base import ContentFile

        # Generate the QR code
        qr = qrcode.QRCode(border=2)
        qr.add_data(f'https://spplane.app/register/qrr/{instance.unique_id}')
        qr.make(fit=True)
        img_qr = qr.make_image()

        # Save the QR code image to a buffer
        buffer = BytesIO()
        img_qr.save(buffer, format='PNG')
        buffer.seek(0)

        # Create and save the QRCode instance
        qr_code_instance = QRCode(
            contact_list=instance,
            qr_data=f'https://spplane.app/register/qrr/{instance.unique_id}',
        )
        qr_code_instance.qr_image.save(
            f'{instance.unique_id}.png', ContentFile(buffer.read())
        )
        qr_code_instance.save()
