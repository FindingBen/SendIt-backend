# Generated by Django 4.2.2 on 2024-05-12 16:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0007_alter_contactlist_created_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='total_overall_progress',
            field=models.IntegerField(default=0),
        ),
    ]