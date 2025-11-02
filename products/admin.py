from django.contrib import admin
from .models import Product, ShopifyWebhookLog
# Register your models here.

admin.site.register(Product)
admin.site.register(ShopifyWebhookLog)
