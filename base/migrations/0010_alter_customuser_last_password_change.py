# Generated by Django 4.2.2 on 2024-05-19 09:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0009_customuser_last_password_change'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customuser',
            name='last_password_change',
            field=models.DateField(blank=True, null=True),
        ),
    ]
