# Generated by Django 4.2.2 on 2023-11-13 20:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='message_name',
            field=models.CharField(default='Content 1', max_length=20),
        ),
    ]