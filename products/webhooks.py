from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from backend import settings
from django.http import HttpResponse
from base.models import ShopifyStore
from decimal import Decimal
from .analyzers import ProductAnalyzer
from .models import ShopifyWebhookLog, Product, ProductScore, RulesPattern, ProductMedia
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
        img_field = (data.get("image") or {}).get("src")

        variants = data.get("variants", [])
   
        if not variants:
            return HttpResponse({"message": "No variants found, nothing to create."}, status=200)
        print('sssaaaaaa')
        created_variants = []
        skipped_variants = []
        product_images = data.get("images", []) or []
        image_map = {img.get("id"): img.get("src") for img in product_images if isinstance(img, dict)}

        for variant in variants:

            shopify_id = variant.get("admin_graphql_api_id")
            variant_name = variant.get("title", None)
            image_id = variant.get("image_id",None)
            sku = variant.get("sku",None)
            barcode = variant.get("barcode",None)
            price = variant.get("price",None)
            color = variant.get("option1",None)
            size = variant.get("option2",None)
            #v_image = variant.get("image") or []
            
            variant_image = None

            variant_image = None
            if image_id and image_id in image_map:
                variant_image = image_map[image_id]
            else:
                # Fallback: find via variant_ids list in images if image_id is missing
                for img in product_images:
                    variant_ids = img.get("variant_ids", []) or []
                    if variant.get("id") in variant_ids:
                        variant_image = img.get("src")
                        break

            variant_image = variant_image or (data.get("image") or {}).get("src")
            final_title = title
            if variant:
                vn = variant_name.strip()
                if vn and vn.lower() != "default title":
                    final_title = f'{final_title}-{vn}'
            #variant_images = v_image
            obj, created = Product.objects.get_or_create(
                product_id=product_id,
                shopify_id=shopify_id,
                shopify_store=store_obj,
                title=final_title,
                sku=sku,
                barcode=barcode,
                color=color,
                size=size,
                category=category,
                img_field=variant_image or img_field,
                price=price if price else None,
                variant=True if len(variants) > 1 else False,
                synced_with_shopify=True,
            )

            if created:
                for parent_img in product_images:

                    ProductMedia.objects.update_or_create(
                        shopify_media_id=parent_img.get("id"),
                                defaults={
                                    "product": obj,
                                    "src": parent_img.get("src"),
                                    "shopify_media_id": parent_img.get("id"),
                                    "alt_text": parent_img.get("alt") or "",
                        }
                    )
                    
                product_score = ProductScore.objects.create(product=obj)
                rules = RulesPattern.objects.get(store=store_obj)

                variables = {
                            "product": obj,
                            "rules": rules,
                            "product_id": product_id,
                            "parent_images": product_images,
                            "variant_images": []
                        }

                product_analysis = ProductAnalyzer.analyze_product(variables)

                if product_analysis:
                    product_score.seo_score = Decimal(product_analysis["seo_score"])
                    product_score.completeness = Decimal(product_analysis["completeness"])
                    product_score.save()

            created_variants.append(shopify_id)

        return HttpResponse(
            {
                "message": "Product variants processed successfully.",
                "created": created_variants,
                "skipped": skipped_variants,
            },
            status=201,
        )

    except Exception as e:
        print("Error processing product webhook:", str(e))
        return HttpResponse({"error": str(e)}, status=500)