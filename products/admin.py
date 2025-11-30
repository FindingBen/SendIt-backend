from django.contrib import admin
from .models import Product, RulesPattern,ShopifyWebhookLog, ProductScore, ProductMedia
# Register your models here.

admin.site.register(Product)
admin.site.register(RulesPattern)
admin.site.register(ProductScore)
admin.site.register(ShopifyWebhookLog)
admin.site.register(ProductMedia)
