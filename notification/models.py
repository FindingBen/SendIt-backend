from django.db import models
from django.conf import settings
from base.models import User, ShopifyStore
from products.models import ProductDraft
import uuid


class Notification(models.Model):
    NOTIF_TYPES = [
        ('success', 'success'),
        ('error', 'error')
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='notifications')
    notif_type = models.CharField(max_length=30, choices=NOTIF_TYPES)
    message = models.TextField(max_length=2020)
    title = models.CharField(max_length=255, default='Default title')
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user} - {self.notif_type} - {self.message[:20]}"

class OptimizationJob(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    product_id = models.CharField(max_length=255)
    store = models.ForeignKey(ShopifyStore, on_delete=models.CASCADE, null=True)
    product_draft = models.ForeignKey(ProductDraft, on_delete=models.CASCADE, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    error = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(blank=True, null=True)