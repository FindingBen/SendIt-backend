from django.db import models
from django.conf import settings
from base.models import User
# Create your models here.


class Notification(models.Model):
    NOTIF_TYPES = [
        ('success', 'password_change'),
        ('success', 'purchase'),
        ('error', 'purchase_error'),
        ('error', 'send_error'),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='notifications')
    notif_type = models.CharField(max_length=30, choices=NOTIF_TYPES)
    message = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user} - {self.notif_type} - {self.message[:20]}"
