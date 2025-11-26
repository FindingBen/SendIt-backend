from django.http import HttpResponse, JsonResponse
from base.models import ShopifyStore, CustomUser, Contact, ContactList
from products.models import ShopifyWebhookLog
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from datetime import datetime
import hmac
import hashlib
import base64
import json
import logging


logger = logging.getLogger(__name__)
environment = settings.ENVIRONMENT

@csrf_exempt
@require_http_methods(['POST'])
def customer_shop_redact_request_webhook(request):
    """Deleting shop and associated user upon Shopify's request."""
    shopify_hmac = request.META.get('HTTP_X_SHOPIFY_HMAC_SHA256')

    if not shopify_hmac:
        logger.warning("Missing HMAC header in shop redact webhook.")
        return HttpResponse("Missing signature", status=400)
    try:
        body = request.body
        expected_hmac = base64.b64encode(
            hmac.new(settings.SHOPIFY_API_SECRET.encode(),
                     body, hashlib.sha256).digest()
        ).decode()

        if not hmac.compare_digest(expected_hmac, shopify_hmac):
            logger.warning("Invalid HMAC signature.")
            return HttpResponse("Unauthorized", status=401)

        data = json.loads(body)
        shop_domain = data.get('shop_domain')
        if not shop_domain:
            logger.error("Shop domain missing in payload.")
            return HttpResponse("Bad request", status=400)
        try:
            shop = ShopifyStore.objects.get(shop_domain=shop_domain)
            user = CustomUser.objects.filter(custom_email=shop.email).first()

            shop.delete()
            if user:
                user.is_active = False
                user.shopify_connect = False
                user.scheduled_package = None
                user.package_plan = 1
                user.save()

            logger.info(f"Shopify store '{shop_domain}' deleted successfully.")
            return HttpResponse(status=200)

        except ShopifyStore.DoesNotExist:
            logger.warning(f"ShopifyStore not found for domain: {shop_domain}")
            return HttpResponse(status=404)
    except Exception as e:
        logger.exception("Unhandled error in shop redact webhook.")
        return JsonResponse({"error": str(e)}, status=500)
    

@require_http_methods(['POST'])
@csrf_exempt
def customer_redact_request_webhook(request):
    """Removing customer data upon Shopify's request."""
    shopify_hmac = request.META.get('HTTP_X_SHOPIFY_HMAC_SHA256', '').strip()
    if not shopify_hmac:
        logger.warning("Missing HMAC header in customer redact webhook.")
        return HttpResponse("Missing signature", status=400)

    try:
        body = request.body  # read raw body once
        computed_hmac = hmac.new(
            settings.SHOPIFY_API_SECRET.encode(),
            body,
            hashlib.sha256
        ).digest()

        expected_hmac = base64.b64encode(computed_hmac)
        received_hmac = shopify_hmac.encode()

        if not hmac.compare_digest(expected_hmac, received_hmac):
            logger.warning("Invalid HMAC signature.")
            return HttpResponse("Unauthorized", status=401)

        # HMAC passed, parse body
        data = json.loads(body)
        logger.info(f"Customer redact webhook payload: {data}")
        shop_domain = data.get('shop_domain')
        customer_id = data.get('customer', {}).get('id')
        print(customer_id)

        if not shop_domain:
            logger.error("Shop domain missing in payload.")
            return HttpResponse("Bad request", status=400)

        with transaction.atomic():
            deleted, _ = Contact.objects.filter(
                custom_id=f'gid://shopify/Customer/{customer_id}'
            ).delete()

            if deleted:
                logger.info(
                    f"Customer with id {customer_id} redacted for shop: {shop_domain}")
            else:
                logger.info("Contact already deleted or not found — skipping.")

        return HttpResponse(status=200)

    except Exception as e:
        logger.exception("Unhandled error in customer redact webhook.")
        return JsonResponse({"error": str(e)}, status=500)
    
@require_http_methods(['POST'])
@csrf_exempt
def customer_data_request_webhook(request):
    """Handling customer data request webhook from Shopify."""
    shopify_hmac = request.META.get('HTTP_X_SHOPIFY_HMAC_SHA256')
    if shopify_hmac:

        body = request.body
        hashit = hmac.new(settings.SHOPIFY_API_SECRET.encode(
            'utf-8'), body, hashlib.sha256)
        calculated_hmac = base64.b64encode(hashit.digest()).decode()

        if not hmac.compare_digest(calculated_hmac, shopify_hmac):
            return HttpResponse(status=401)  # Unauthorized

        data = json.loads(body)

        print('Webhook triggered! We are not storing customers data with this webhook.')

        return HttpResponse(status=200)
    return HttpResponse({"error": "Missing shopify signature!"}, status=500)

@require_http_methods(['POST'])
@csrf_exempt
def create_customer_webhook(request):
    print('Creating customer webhook...',request)
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
        print(data)
        customer_id = data.get("admin_graphql_api_id")
        first_name = data.get("first_name") or ""
        last_name = data.get("last_name") or ""
        phone = data.get("phone")
        sms_opt_in = "SUBSCRIBED" if phone else "NOT_SUBSCRIBED"
        created_at = data.get("created_at")
        created_date = None
  
        user = CustomUser.objects.get(email=store_obj.email)
        if created_at:
            try:
                created_date = datetime.fromisoformat(created_at.replace("Z", "+00:00")).date()
            except Exception:
                created_date = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S%z").date()
        contact_list = ContactList.objects.filter(users=user, shopify_list=True).first()
        if not contact_list:
            contact_list = ContactList.objects.create(users=user, name="Shopify Contacts", shopify_list=True)
        can_add, error_msg = user.can_add_contact()
        print(can_add, error_msg)
        if not can_add:
            print(f"Contact limit reached: {error_msg}")
            return HttpResponse(
                json.dumps({"error": error_msg}),
                content_type="application/json",
                status=400
            )
        contact, created = Contact.objects.get_or_create(
            custom_id=customer_id,
            defaults={
                "users": user,
                "contact_list": contact_list,
                "first_name": first_name,
                "last_name": last_name,
                "phone_number": phone,
                "is_shopify_contact": True,
                "sms_opt_in": sms_opt_in,
                "created_at": created_date
            },
        )
        return HttpResponse({"message": "Customer webhook processed."}, status=200)
    except Exception as e:
        print("Error processing customer webhook:", str(e))
        return HttpResponse({"error": str(e)}, status=500)