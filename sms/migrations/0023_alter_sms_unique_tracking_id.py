# Generated by Django 4.2.16 on 2025-07-13 19:15

from django.db import migrations, models
import shortuuid.main


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0022_alter_sms_unique_tracking_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sms',
            name='unique_tracking_id',
            field=models.CharField(default=shortuuid.main.ShortUUID.uuid, max_length=22, unique=True),
        ),
    ]
