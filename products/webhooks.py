from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from backend import settings
from django.http import HttpResponse
from base.models import ShopifyStore
from .models import ShopifyWebhookLog, Product
import json



@csrf_exempt
@require_http_methods(['POST'])
def create_product_webhook(request):
    print('Creating product webhook...',request)
    shopify_webhook_id = request.META.get('HTTP_X_SHOPIFY_WEBHOOK_ID')
    shopify_domain = request.META.get('HTTP_X_SHOPIFY_SHOP_DOMAIN')
    shopify_topic = request.META.get('HTTP_X_SHOPIFY_TOPIC')
    created_at = request.META.get('HTTP_X_SHOPIFY_TRIGGERED_AT')
    print(shopify_webhook_id)
    if ShopifyWebhookLog.objects.filter(webhook_id=shopify_webhook_id).exists():
        print("⚠️ Duplicate webhook ignored:", shopify_webhook_id)
        return HttpResponse(status=208)  # Acknowledge but skip

    store_obj = ShopifyStore.objects.filter(shop_domain=shopify_domain).first()

    ShopifyWebhookLog.objects.create(webhook_id=shopify_webhook_id, 
        webhook_topic=shopify_topic, shopify_store=store_obj,created_at=created_at)

    try:
        data = json.loads(request.body)
        print(data)
        product_id = data.get("admin_graphql_api_id")
        title = data.get("title", "Untitled Product")
        category = (
            data.get("category", {}).get("full_name")
            or data.get("product_type", "")
        )
        img_field = data.get("image", {}).get("src")

        variants = data.get("variants", [])

        if not variants:
            return HttpResponse({"message": "No variants found, nothing to create."}, status=200)

        created_variants = []
        skipped_variants = []
        product_images = data.get("images", []) or []
        image_map = {img.get("id"): img.get("src") for img in product_images if isinstance(img, dict)}

        for variant in variants:
            shopify_id = variant.get("admin_graphql_api_id")
            variant_name = variant.get("title", None)
            image_id = variant.get("image_id")
            sku = variant.get("sku")
            barcode = variant.get("barcode")
            price = variant.get("price")
            color = variant.get("option1",None)
            size = variant.get("option2",None)
            
            variant_image = None

            variant_image = None
            if image_id and image_id in image_map:
                variant_image = image_map[image_id]
            else:
                # Fallback: find via variant_ids list in images if image_id is missing
                for img in product_images:
                    variant_ids = img.get("variant_ids", [])
                    if variant.get("id") in variant_ids:
                        variant_image = img.get("src")
                        break

            variant_image = variant_image or (data.get("image") or {}).get("src")

            Product.objects.create(
                product_id=product_id,
                shopify_id=shopify_id,
                shopify_store=store_obj,
                title=variant_name if variant_name else title,
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