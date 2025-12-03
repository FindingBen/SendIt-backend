from .models import Product, ProductDraft, ProductMedia, ProductMediaDraft
from django.db import transaction

def create_product_draft(product: Product):
    """
    Creates or updates a draft copy of a product and all image/media entries.
    Uses shopify_id as the unique draft identifier.
    """

    with transaction.atomic():

        # 1️⃣ Create or update the ProductDraft
        draft, created = ProductDraft.objects.update_or_create(
            shopify_id=product.shopify_id,     # IDENTIFIER
            defaults={
                "product_id": product.product_id,
                "parent_product_id": product.parent_product_id,
                "shopify_store": product.shopify_store,
                "title": product.title,
                "sku": product.sku,
                "barcode": product.barcode,
                "color": product.color,
                "size": product.size,
                "category": product.category,
                "img_field": product.img_field,
                "variant": product.variant,
                "price": product.price,
                "synced_with_shopify": product.synced_with_shopify,
            }
        )

        # 2️⃣ Copy all media from ProductMedia → ProductMediaDraft
        media_list = ProductMedia.objects.filter(product=product)

        for media in media_list:
            ProductMediaDraft.objects.update_or_create(
                shopify_media_id=media.shopify_media_id,  # unique constraint
                defaults={
                    "product": draft,
                    "src": media.src,
                    "alt_text": media.alt_text,
                }
            )

    return draft
