from django.db import models


class RulesPattern(models.Model):
    """Rule pattern for product filling information"""
    store = models.ForeignKey('base.ShopifyStore', on_delete=models.CASCADE)
    product_name_rule = models.CharField(max_length=255, blank=True, null=True)
    product_description_rule = models.CharField(max_length=255, blank=True, null=True)
    product_image_rule = models.CharField(max_length=255, blank=True, null=True)
    product_variant_rule = models.CharField(max_length=255, blank=True, null=True)
    product_tag_rule = models.CharField(max_length=255, null=True, blank=True)
    product_alt_image_rule = models.CharField(max_length=255, null=True, blank=True)
    keywords = models.CharField(max_length=255, blank=True, null=True)
    min_title_length = models.IntegerField(default=20)
    max_title_length = models.IntegerField(default=70)
    product_description_template = models.TextField(blank=True, null=True)

    min_description_length = models.IntegerField(default=120)
    max_description_length = models.IntegerField(default=300)

    max_alt_desc_length = models.IntegerField(default=30)

    min_images = models.IntegerField(default=1)
    requires_alt_text = models.BooleanField(default=True)

class Product(models.Model):
    product_id=models.CharField(max_length=255, unique=False)
    parent_product_id=models.CharField(max_length=255, blank=True, null=True)
    shopify_id = models.CharField(max_length=255, unique=True)
    shopify_store = models.ForeignKey('base.ShopifyStore', on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    seo_description = models.TextField(max_length=161,blank=True, null=True)
    static_desc = models.BooleanField(default=False)
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
    
class ProductVariant(models.Model):
    parent_product = models.ForeignKey(Product, on_delete=models.CASCADE)
    name = models.CharField(max_length=255, blank=True, null=True)
    sku = models.CharField(max_length=50, blank=True, null=True)
    barcode = models.CharField(max_length=50, blank=True, null=True)
    img_field = models.URLField(max_length=500, blank=True, null=True)

class ProductVariantDraft(models.Model):
    parent_product = models.ForeignKey(Product, on_delete=models.CASCADE)
    name = models.CharField(max_length=255, blank=True, null=True)
    sku = models.CharField(max_length=50, blank=True, null=True)
    barcode = models.CharField(max_length=50, blank=True, null=True)
    img_field = models.URLField(max_length=500, blank=True, null=True)

class ProductDraft(models.Model):
    product_id=models.CharField(max_length=255, unique=False)
    parent_product_id=models.CharField(max_length=255, blank=True, null=True)
    shopify_id = models.CharField(max_length=255, unique=True)
    shopify_store = models.ForeignKey('base.ShopifyStore', on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    seo_description = models.TextField(max_length=161,blank=True, null=True)
    static_desc = models.BooleanField(default=False)
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
    
class ProductTag(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    tag_name = models.CharField(max_length=100, blank=True, null=True)

class ProductTagDraft(models.Model):
    product = models.ForeignKey(ProductDraft, on_delete=models.CASCADE)
    tag_name = models.CharField(max_length=100, blank=True, null=True)

class ProductMediaDraft(models.Model):
    product = models.ForeignKey(ProductDraft, on_delete=models.CASCADE)
    shopify_media_id = models.CharField(max_length=255, unique=True)
    field_id = models.CharField(max_length=255, null=True, blank=True)
    src = models.URLField(max_length=500, blank=True, null=True)
    alt_text = models.TextField(blank=True, null=True)
    
class ProductMedia(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    shopify_media_id = models.CharField(max_length=255, unique=True)
    field_id = models.CharField(max_length=255, null=True, blank=True)
    src = models.URLField(max_length=500, blank=True, null=True)
    alt_text = models.TextField(blank=True, null=True)



class ProductScore(models.Model):
    product = models.OneToOneField(
    Product,
    on_delete=models.CASCADE,
    related_name="score"
    )
    seo_score = models.DecimalField(default=0.0,decimal_places=2,max_digits=5)
    completeness = models.DecimalField(default=0.0,decimal_places=2,max_digits=5)



class ShopifyWebhookLog(models.Model):
    shopify_store = models.ForeignKey('base.ShopifyStore', on_delete=models.CASCADE)
    webhook_topic = models.CharField(max_length=255)
    webhook_id = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Webhook {self.webhook_topic} for {self.shopify_store.shop_domain} at {self.created_at}"