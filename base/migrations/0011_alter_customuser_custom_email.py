# Generated by Django 4.2.2 on 2023-12-30 11:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0010_customuser_custom_email'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customuser',
            name='custom_email',
            field=models.EmailField(default=1, max_length=254, unique=True),
            preserve_default=False,
        ),
    ]