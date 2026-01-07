from django.db import transaction
from .models import Product, ProductDraft, ProductMedia, ProductMediaDraft, RulesPattern,ProductScore
from typing import Optional, Dict, Any
from .analyzers import ProductAnalyzer
from decimal import Decimal



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
                    "field_id":media.field_id,
                    "alt_text": media.alt_text,
                }
            )

    return draft



def generate_unique_sku(title: str = "", attributes: Optional[Dict[str, Any]] = None) -> str:
    """
    Build SKU like: <TITLE_PREFIX>-<ATTRS>-<4hex>
    - TITLE_PREFIX: first letters of the first 3 words in the title (uppercased), e.g. "Shoulder Strap for Injury" -> "SSF"
    - ATTRS: optional parts derived from attributes dict (color -> first 3 letters upper, size -> mapped code)
    - unique 4 char hex suffix (lowercase), e.g. "f231"

    Usage:
      generate_unique_sku("Shoulder Strap for Injury", {"color": "Blue", "size": "Medium"})
      -> "SSF-BLU-M-f231"
    """
    import re
    import secrets

    attributes = attributes or {}

    # Title prefix: first letter of up to first 3 words
    words = re.findall(r"\w+", (title or "").strip())
    prefix_letters = [w[0].upper() for w in words[:3]]
    prefix = "".join(prefix_letters) if prefix_letters else "PRD"

    # Attributes part
    parts = []
    color = attributes.get("color") or attributes.get("colour")
    if color:
        # use first 3 alpha chars of color uppercased (pad/truncate)
        col = re.sub(r"[^A-Za-z0-9]", "", str(color)).upper()
        parts.append(col[:3] if len(col) >= 3 else col)

    size = attributes.get("size")
    if size:
        s = str(size).strip().lower()
        size_map = {
            "xs": "XS", "extra small": "XS",
            "s": "S", "small": "S",
            "m": "M", "medium": "M",
            "l": "L", "large": "L",
            "xl": "XL", "extra large": "XL",
            "xxl": "XXL",
        }
        code = size_map.get(s, None)
        if not code:
            # if single-letter provided (e.g. "M") or unknown, use upcased first 2 chars
            code = s.upper()[:2] if s else ""
        if code:
            parts.append(code)

    # unique 4 hex chars
    uniq = secrets.token_hex(2)

    sku_parts = [prefix]
    if parts:
        sku_parts.extend(parts)
    sku_parts.append(uniq)

    return "-".join(p for p in sku_parts if p)


def generate_unique_barcode() -> str:
    """
    Generate a unique barcode for the given product variant.
    This is a placeholder implementation and should be replaced with actual logic
    to ensure uniqueness across all products in the database.
    """
    import random

    while True:
        # Generate a random 12-digit numeric barcode
        barcode = ''.join([str(random.randint(0, 9)) for _ in range(12)])
        # Check if barcode is unique
        if not Product.objects.filter(barcode=barcode).exists():
            return barcode
        

def score_product_quality(store_obj, product:Product) -> bool:
    """
    Docstring for score_product_quality
    
    :param store_obj: Description
    :param product: Description
    :type product: Product
    :return: Description
    :rtype: bool
    """
    medias = ProductMedia.objects.filter(product=product)
    rules = RulesPattern.objects.filter(store=store_obj).first()

    product_score, created = ProductScore.objects.get_or_create(product=product)

    variables = {
                "product": product,
                "rules": rules,
                "product_id": product.product_id,
                "parent_images": medias,
                "variant_images": [],
    }

    analysis = ProductAnalyzer.analyze_product(variables)

    if analysis:
        product_score.seo_score = Decimal(analysis.get("seo_score", 0))
        product_score.completeness = Decimal(analysis.get("completeness", 0))
        product_score.save()
        return True
    return False