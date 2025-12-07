from django.contrib import admin
from .models import Product, RulesPattern,ShopifyWebhookLog, ProductScore, ProductVariantDraft,ProductVariant,ProductMedia, ProductDraft, ProductMediaDraft
# Register your models here.

admin.site.register(Product)
admin.site.register(RulesPattern)
admin.site.register(ProductScore)
admin.site.register(ShopifyWebhookLog)
admin.site.register(ProductMedia)
admin.site.register(ProductDraft)
admin.site.register(ProductMediaDraft)
admin.site.register(ProductVariantDraft)
admin.site.register(ProductVariant)
