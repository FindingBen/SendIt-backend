# Generated by Django 4.2.2 on 2024-05-18 20:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0008_message_total_overall_progress'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='last_password_change',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
