from django.db import models

# Create your models here.

class Product(models.Model):
    product_id=models.CharField(max_length=255, unique=False)
    shopify_id = models.CharField(max_length=255, unique=True)
    shopify_store = models.ForeignKey('base.ShopifyStore', on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    sku = models.CharField(max_length=50, blank=True, null=True)
    barcode = models.CharField(max_length=50, blank=True, null=True)
    color = models.CharField(max_length=100, blank=True, null=True)
    size = models.CharField(max_length=100, blank=True, null=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    img_field = models.URLField(max_length=500, blank=True, null=True)
    variant = models.BooleanField(default=False)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    synced_with_shopify = models.BooleanField(default=False)

    def __str__(self):
        return self.title