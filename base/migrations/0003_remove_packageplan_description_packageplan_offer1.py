# Generated by Django 4.2 on 2023-07-04 08:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0002_alter_contact_user_alter_contactlist_users_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='packageplan',
            name='description',
        ),
        migrations.AddField(
            model_name='packageplan',
            name='offer1',
            field=models.CharField(max_length=200, null=True),
        ),
    ]