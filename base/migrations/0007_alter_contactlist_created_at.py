# Generated by Django 4.2.2 on 2024-05-05 18:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0006_alter_contact_users'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contactlist',
            name='created_at',
            field=models.DateField(auto_now_add=True),
        ),
    ]