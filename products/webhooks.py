from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from backend import settings
from django.db import transaction
from django.http import HttpResponse
from base.models import ShopifyStore
from decimal import Decimal
from .analyzers import ProductAnalyzer
from .models import ShopifyWebhookLog, Product,ProductVariant, ProductTag,ProductScore, RulesPattern, ProductMedia
from .helpers import score_product_quality
import json



@csrf_exempt
@require_http_methods(['POST'])
def create_product_webhook(request):
    print('Creating product webhook...')
    shopify_webhook_id = request.META.get('HTTP_X_SHOPIFY_WEBHOOK_ID')
    shopify_domain = request.META.get('HTTP_X_SHOPIFY_SHOP_DOMAIN')
    shopify_topic = request.META.get('HTTP_X_SHOPIFY_TOPIC')
    created_at = request.META.get('HTTP_X_SHOPIFY_TRIGGERED_AT')

    if ShopifyWebhookLog.objects.filter(webhook_id=shopify_webhook_id).exists():
        print("⚠️ Duplicate webhook ignored:", shopify_webhook_id)
        return HttpResponse(status=208)  # Acknowledge but skip

    store_obj = ShopifyStore.objects.filter(shop_domain=shopify_domain).first()
    print('Store object:', store_obj)
    ShopifyWebhookLog.objects.create(webhook_id=shopify_webhook_id, 
        webhook_topic=shopify_topic, shopify_store=store_obj,created_at=created_at)

    try:
        data = json.loads(request.body)
        product_id = data.get("admin_graphql_api_id")
        title = data.get("title", "Untitled Product")
        category = (
            data.get("category", {}).get("full_name")
            or data.get("product_type", "")
        )
        print(data)
        tags = data.get("tags", []) or []
        img_field = (data.get("image") or {}).get("src")
        variants = data.get("variants", [])

        if not product_id:
            return HttpResponse({"message": "Missing product ID"}, status=400)

        # ---------------------------------------------------------------------
        # FALLBACK: no variants?
        # ---------------------------------------------------------------------
        if not variants:
            return HttpResponse({"message": "No variants found"}, status=200)

        # ---------------------------------------------------------------------
        # BUILD IMAGE MAP (Shopify images array)
        # ---------------------------------------------------------------------
        product_images = data.get("media", []) or []
        image_map = {img.get("admin_graphql_api_id"): img.get("preview_image").get('src') for img in product_images if isinstance(img, dict)}
        print('STEP 1')
        # ---------------------------------------------------------------------
        # CREATE / UPDATE PARENT PRODUCT
        # ---------------------------------------------------------------------
        parent_defaults = {
            "product_id": product_id,
            "parent_product_id": product_id,
            "shopify_store": store_obj,
            "title": title,
            "description": data.get("body_html") or "",
            "seo_description": None,  # Shopify webhook does not send SEO meta normally
            "img_field": img_field,
            "variant": True if len(variants) > 1 else False,
            "category": category,
            "synced_with_shopify": True,
        }

        parent_obj, parent_created = Product.objects.update_or_create(
            shopify_id=product_id,
            defaults=parent_defaults,
        )
        print('STEP 2')
        # ---------------------------------------------------------------------
        # SAVE TAGS (only when parent created)
        # ---------------------------------------------------------------------
        if parent_created:
            for tag in tags:
                ProductTag.objects.get_or_create(product=parent_obj, tag_name=tag)
        print('STEP 3')
        # -----------  ----------------------------------------------------------
        # SAVE PRODUCT MEDIA
        # ---------------------------------------------------------------------
        for img in product_images:
            ProductMedia.objects.update_or_create(
                shopify_media_id=img.get("admin_graphql_api_id"),
                defaults={
                    "product": parent_obj,
                    "src": img.get("preview_image").get("src"),
                    "alt_text": img.get("alt") or "",
                    "field_id": img.get("id"),   # similar to main pipeline
                },
            )
        print('STEP 4')
        # ---------------------------------------------------------------------
        # PROCESS VARIANTS
        # ---------------------------------------------------------------------
        created_variants = []
        skipped_variants = []

        for variant in variants:

            v_id = variant.get("admin_graphql_api_id")
            variant_name = variant.get("title")
            image_id = variant.get("image_id")

            sku = variant.get("sku")
            barcode = variant.get("barcode")
            # price = variant.get("price")
            # color = variant.get("option1")
            # size = variant.get("option2")

            # ---------------------- IMAGE RESOLUTION -------------------------
            variant_image = None

            if image_id and image_id in image_map:
                variant_image = image_map[image_id]
            else:
                for img in product_images:
                    if variant.get("id") in (img.get("variant_ids") or []):
                        variant_image = img.get("src")
                        break
            print('STEP 5')
            variant_image = variant_image or img_field

            # ---------------------- VARIANT NAME LOGIC -----------------------
            pv_name = variant_name.strip() if variant_name and variant_name.lower() != "default title" else v_id

            # ---------------------- UPSERT VARIANT ---------------------------
            pv_defaults = {
                "sku": sku,
                "barcode": barcode,
                "img_field": variant_image,
                # "price": Decimal(price) if price else None
            }

            try:
                pv_obj, pv_created = ProductVariant.objects.update_or_create(
                    parent_product=parent_obj,
                    name=pv_name,
                    defaults=pv_defaults,
                )
                if pv_created:
                    created_variants.append(v_id)
                else:
                    skipped_variants.append(v_id)

            except Exception as e:
                print("Variant upsert failed:", v_id, str(e))
                skipped_variants.append(v_id)
                continue

        # ---------------------------------------------------------------------
        # CREATE SCORE + ANALYSIS ONLY ON PARENT CREATION
        # ---------------------------------------------------------------------
        if parent_created:
            score_product = score_product_quality(store_obj,parent_obj)
        # ---------------------------------------------------------------------
        # RESPONSE
        # ---------------------------------------------------------------------
            if score_product:
                return HttpResponse(
                    {
                        "message": "Product processed successfully",
                        "created_variants": created_variants,
                        "skipped_variants": skipped_variants,
                    },
                    status=201,
                )
            else:
                    return HttpResponse(
                        {
                            "message": "Product processed successfully, score not applied, contact support",
                            "created_variants": created_variants,
                            "skipped_variants": skipped_variants,
                        },
                        status=202,
                    )

    except Exception as e:
        print("Error processing product webhook:", str(e))
        return HttpResponse({"error": str(e)}, status=500)
    
@csrf_exempt
@require_http_methods(['POST'])
def delete_product_webhook(request):
    shopify_webhook_id = request.META.get('HTTP_X_SHOPIFY_WEBHOOK_ID')
    shopify_domain = request.META.get('HTTP_X_SHOPIFY_SHOP_DOMAIN')
    shopify_topic = request.META.get('HTTP_X_SHOPIFY_TOPIC')
    created_at = request.META.get('HTTP_X_SHOPIFY_TRIGGERED_AT')

    if ShopifyWebhookLog.objects.filter(webhook_id=shopify_webhook_id).exists():
        print("⚠️ Duplicate webhook ignored:", shopify_webhook_id)
        return HttpResponse(status=208)  # Acknowledge but skip
    print('SSSSSSS')
    store_obj = ShopifyStore.objects.filter(shop_domain=shopify_domain).first()
    print('Store object:', store_obj)
    ShopifyWebhookLog.objects.create(webhook_id=shopify_webhook_id, 
        webhook_topic=shopify_topic, shopify_store=store_obj,created_at=created_at)
    try:
        data = json.loads(request.body)
        print('Webhook data:', data)
        product_id = data.get("id")
        craft_id = "gid://shopify/Product/" + str(product_id)
        Product.objects.filter(shopify_id=craft_id).delete()
        return HttpResponse({"message": "Product deleted successfully"}, status=200)
    except Exception as e:        
        print("Error processing product delete webhook:", str(e))
        return HttpResponse({"error": str(e)}, status=500)
    
@csrf_exempt
@require_http_methods(['POST'])
def update_product_webhook(request):
    shopify_webhook_id = request.META.get('HTTP_X_SHOPIFY_WEBHOOK_ID')
    shopify_domain = request.META.get('HTTP_X_SHOPIFY_SHOP_DOMAIN')
    shopify_topic = request.META.get('HTTP_X_SHOPIFY_TOPIC')
    created_at = request.META.get('HTTP_X_SHOPIFY_TRIGGERED_AT')
    if ShopifyWebhookLog.objects.filter(webhook_id=shopify_webhook_id).exists():
        print("⚠️ Duplicate webhook ignored:", shopify_webhook_id)
        return HttpResponse(status=208)  # Acknowledge but skip
    store_obj = ShopifyStore.objects.filter(shop_domain=shopify_domain).first()
    print('Store object:', store_obj)
    ShopifyWebhookLog.objects.create(webhook_id=shopify_webhook_id, 
        webhook_topic=shopify_topic, shopify_store=store_obj,created_at=created_at)
    

    try:
        data = json.loads(request.body)
        product_id = data.get("admin_graphql_api_id")

        if not product_id:
            return
        with transaction.atomic():
            product_draft, _ = Product.objects.get_or_create(
                shopify_id=product_id,
                shopify_store=store_obj,
                defaults={
                    "product_id": str(data.get("id")),
                    "parent_product_id": str(data.get("id")),
                    "title": data.get("title", ""),
                    "description": data.get("body_html", ""),
                }
            )
            print('updating')
            updated_fields = []
            title = data.get("title")
            if title and title != product_draft.title:
                product_draft.title = title
                updated_fields.append("title")

            # ---- DESCRIPTION ----
            body_html = data.get("body_html")
            if body_html is not None and body_html != product_draft.description:
                product_draft.description = body_html
                updated_fields.append("description")
            print('hereeee')
            images = data.get("media")
            if images:
                for media in images:
                    ProductMedia.objects.update_or_create(
                        shopify_media_id=media.get("admin_graphql_api_id"),
                        defaults={
                            "product": product_draft,
                            "src": media.get("preview_image").get("src"),
                            "alt_text": media.get("alt") or "",
                            "field_id": media.get("id"),   # similar to main pipeline
                        },
                    )
            
            product_draft.save(update_fields=updated_fields)
            updated_fields = []
            update_score = score_product_quality(store_obj, product_draft)
            if update_score:
                return HttpResponse({"message": "Product updated successfully"}, status=200)
            
        return HttpResponse({"message": "Product updated successfully but score hasn't been updated, contact support"}, status=202)
    except Exception as e:        
        print("Error processing product update webhook:", str(e))
        return HttpResponse({"error": str(e)}, status=500)