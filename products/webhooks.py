from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from backend import settings
from django.http import HttpResponse
from base.models import ShopifyStore
from decimal import Decimal
from .analyzers import ProductAnalyzer
from .models import ShopifyWebhookLog, Product,ProductVariant, ProductTag,ProductScore, RulesPattern, ProductMedia
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
        print('VARIANTS:', variants)
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
                print('STEP 6')
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
            medias = ProductMedia.objects.filter(product=parent_obj)
            rules = RulesPattern.objects.filter(store=store_obj).first()
            print('STEP 7')
            product_score = ProductScore.objects.create(product=parent_obj)

            variables = {
                "product": parent_obj,
                "rules": rules,
                "product_id": product_id,
                "parent_images": medias,
                "variant_images": [],
            }

            analysis = ProductAnalyzer.analyze_product(variables)
            if analysis:
                product_score.seo_score = Decimal(analysis.get("seo_score", 0))
                product_score.completeness = Decimal(analysis.get("completeness", 0))
                product_score.save()

        # ---------------------------------------------------------------------
        # RESPONSE
        # ---------------------------------------------------------------------
        return HttpResponse(
            {
                "message": "Product processed successfully",
                "created_variants": created_variants,
                "skipped_variants": skipped_variants,
            },
            status=201,
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