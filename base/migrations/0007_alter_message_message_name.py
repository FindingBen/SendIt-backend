# Generated by Django 4.2.2 on 2023-12-23 10:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0006_surveyresponse_survey_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='message',
            name='message_name',
            field=models.CharField(max_length=40),
        ),
    ]