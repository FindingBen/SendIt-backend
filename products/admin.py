from django.contrib import admin
from .models import Product, RulesPattern,ShopifyWebhookLog, ProductScore
# Register your models here.

admin.site.register(Product)
admin.site.register(RulesPattern)
admin.site.register(ProductScore)
admin.site.register(ShopifyWebhookLog)
