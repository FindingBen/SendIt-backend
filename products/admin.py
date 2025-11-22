from django.contrib import admin
from .models import Product, RulesPattern,ShopifyWebhookLog
# Register your models here.

admin.site.register(Product)
admin.site.register(RulesPattern)
admin.site.register(ShopifyWebhookLog)
