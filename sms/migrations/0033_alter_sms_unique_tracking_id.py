# Generated by Django 4.2.2 on 2024-09-28 13:37

from django.db import migrations, models
import shortuuid.main


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0032_alter_sms_unique_tracking_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sms',
            name='unique_tracking_id',
            field=models.CharField(default=shortuuid.main.ShortUUID.uuid, editable=False, max_length=22, unique=True),
        ),
    ]