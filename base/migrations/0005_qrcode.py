# Generated by Django 4.2.16 on 2024-11-17 11:40

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0004_analyticsdata_total_delivered_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='QRCode',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('qr_image', models.ImageField(blank=True, null=True, upload_to='')),
                ('qr_data', models.CharField(default=None)),
                ('contact_list', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='base.contactlist')),
            ],
        ),
    ]
