from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from backend import settings
from django.http import HttpResponse
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .models import Product,ShopifyWebhookLog, RulesPattern, ProductDraft,ProductMediaDraft,ProductScore, ProductMedia
from decimal import Decimal
from typing import Optional, Dict, Any
from django.db import transaction
from base.models import ShopifyStore, CustomUser
from base.utils import helpers
from base.analyzers import Prompting
from base.auth import get_business_info, OpenAiAuthInit
from base.shopify_functions import ShopifyFactoryFunction
from base.queries import GET_ALL_PRODUCTS,UPDATE_PRODUCT_VARIANTS_BULK,CREATE_WEBHOOK
from .serializers import ProductSerializer
from .analyzers import ProductAnalyzer
from .generatorAi import AiPromptGenerator
from .optimizers import ProductOptimizer
from .helpers import create_product_draft
import json



class ShopifyAuthMixin:
    """
    Reusable helper to resolve shopify store, token and graphql url from request headers.
    Raises ValueError on missing data so callers can return appropriate Response.
    """
    def resolve_shopify(self, request):
        shopify_domain = request.headers.get('shopify-domain', None)
        print(shopify_domain)
        if not shopify_domain:
            raise ValueError("Domain required from shopify!")
        try:

            shopify_store = ShopifyStore.objects.get(shop_domain=shopify_domain)

        except ShopifyStore.DoesNotExist:
            raise ValueError("Shopify store not found in local DB")
        auth = request.headers.get('Authorization', '')
        try:
            shopify_token = auth.split(' ')[1]
        except Exception:
            raise ValueError("Authorization header missing or malformed")
        url = f"https://{shopify_domain}/admin/api/{settings.SHOPIFY_API_VERSION}/graphql.json"
        return shopify_store, shopify_token, url

class ProductView(ShopifyAuthMixin, APIView):

    def get(self, request, id=None, format=None):
        try:
            shopify_store, shopify_token, url = self.resolve_shopify(request)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)

        if id:
            # Get a single product by ID
            try:
                product = Product.objects.select_related("score").get(
                    shopify_store=shopify_store,
                    id=id
                )
                serializer = ProductSerializer(product)
                print(serializer.data)
                return Response(serializer.data)
            except Product.DoesNotExist:
                return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)
        else:
            # Return all products
            products = Product.objects.filter(shopify_store=shopify_store).select_related("score")
            serializer = ProductSerializer(products, many=True)
            return Response(serializer.data)
    


    def put(self, request, format=None):
        try:
            shopify_store, shopify_token, url = self.resolve_shopify(request)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)
       
        data = request.data or {}

        sku = data.get("sku",None)

        barcode = data.get("barcode",None)

        if not sku and not barcode:
            return Response({"error": "Provide 'sku' or 'barcode' to update."}, status=400)
        
        shopify_factory = ShopifyFactoryFunction(
            query=UPDATE_PRODUCT_VARIANTS_BULK, domain=shopify_store.shop_domain, token=shopify_token, url=url, request=request
        )
        products_ids = request.data.get("products", [])
        variants_qs = Product.objects.filter(shopify_store=shopify_store, shopify_id__in=products_ids)

        variants = []

        try:
            from collections import defaultdict
            with transaction.atomic():
                sid = transaction.savepoint()
                original_states = []
                # group payloads by parent product id (full GID)
                grouped = defaultdict(list)
                updated_pks = []

                # first: prepare local updates and group payloads
                for variant in variants_qs:
                    original_states.append({
                        "pk": variant.pk,
                        "sku": variant.sku,
                        "barcode": variant.barcode,
                        "synced_with_shopify": variant.synced_with_shopify,
                    })

                    # generate values only when requested
                    sku_name = None
                    barcode_value = None
                    update_fields = []

                    if sku:
                        sku_name = generate_unique_sku(title=variant.title)
                        variant.sku = sku_name
                        update_fields.append("sku")
                    if barcode:
                        barcode_value = generate_unique_barcode()
                        variant.barcode = barcode_value
                        update_fields.append("barcode")

                    # don't mark synced until Shopify confirms
                    variant.synced_with_shopify = False
                    update_fields.append("synced_with_shopify")
                    variant.save(update_fields=update_fields)

                    # normalize parent product id (must be full GID for Shopify)
                    parent_gid = variant.product_id
                    if parent_gid is None:
                        # try to build if stored numeric
                        try:
                            parent_gid = f"gid://shopify/Product/{int(variant.product_id)}"
                        except Exception:
                            parent_gid = str(variant.product_id)

                    # ensure variant id is full GID
                    vid = str(variant.shopify_id)
                    if not vid.startswith("gid://"):
                        vid = f"gid://shopify/ProductVariant/{vid}"

                    payload = {"id": vid}
                    if sku_name is not None:
                        payload["inventoryItem"] = {"sku": sku_name}
                    if barcode_value is not None:
                        payload["barcode"] = str(barcode_value)

                    grouped[parent_gid].append(payload)
                    updated_pks.append(variant.pk)

                if not grouped:
                    transaction.savepoint_rollback(sid)
                    return Response({"error": "No valid variants to update"}, status=400)

                # second: call Shopify per parent product
                for parent_gid, variants_payload in grouped.items():
                    variables = {
                        "productId": parent_gid,
                        "variants": variants_payload,
                        "allowPartialUpdates": True
                    }
                    response = shopify_factory.update_product_variants(variables)
                    if getattr(response, "status_code", None) != 200:
                        transaction.savepoint_rollback(sid)
                        return Response({"error": "Failed to update product variants on Shopify", "details": getattr(response, "text", str(response))}, status=502)
                    resp_json = response.json()
                    user_errors = resp_json.get("data", {}).get("productVariantsBulkUpdate", {}).get("userErrors", [])
                    if user_errors:
                        transaction.savepoint_rollback(sid)
                        return Response({"error": "Shopify returned user errors", "details": user_errors}, status=400)

                # success: mark only updated variants as synced
                Product.objects.filter(pk__in=updated_pks).update(synced_with_shopify=True)

        except Exception as e:
            return Response({"error": "Exception during update", "details": str(e)}, status=500)

        return Response({"message": "Successfully generated!"}, status=201)
    
class PromptAnalysis(ShopifyAuthMixin, APIView):

    def get(self, request, format=None):
        try:

            shopify_store, shopify_token, url = self.resolve_shopify(request)

        except ValueError as e:
            return Response({"error": str(e)}, status=400)
        
        try:
            client = OpenAiAuthInit().clientAuth()
            
            business_info = get_business_info(shopify_store, shopify_token)
            
            prompt_response = Prompting.init_process(client,business_info)

            rules = prompt_response["recommended_seo_ruleset"]

            with transaction.atomic():
                business_ruleset = RulesPattern.objects.create(
                store=shopify_store,
                product_name_rule=rules["product_name_rule"],
                product_description_rule=rules["product_description_rule"],
                product_image_rule=rules["product_image_rule"],
                product_variant_rule=rules["product_variant_rule"],
                product_tag_rule=rules["product_tag_rule"],
                product_alt_image_rule=rules["product_alt_image_rule"],
                )

                custom_user = CustomUser.objects.get(custom_email=shopify_store.email)
                custom_user.shopify_business_ruleset = True
                custom_user.save()


            return Response({"Successfully created business analysis rules"}, status=200)
        except Exception as e:
            return Response({"error": "Exception during analysis", "details": str(e)}, status=500)


class ProductOptimizeView(ShopifyAuthMixin, APIView):

    def get(self, request, format=None):
        try:
            shopify_store, shopify_token, url = ShopifyAuthMixin().resolve_shopify(request)
            
            product_id = request.query_params.get("product_id")
            print('PARAM',product_id)
            if not product_id:
                return Response({"error": "product_id query parameter is required"}, status=400)

            try:
                product_draft = ProductDraft.objects.get(product_id=product_id, shopify_store=shopify_store)
            except ProductDraft.DoesNotExist:
                return Response({"error": "Draft for this product does not exist"}, status=404)

            media_drafts = ProductMediaDraft.objects.filter(product=product_draft)

            try:
                original_product = Product.objects.get(shopify_id=product_draft.shopify_id)
            except Product.DoesNotExist:
                original_product = None

            response = {
                "draft": {
                    "product": {
                        "id": product_draft.product_id,
                        "title": product_draft.title,
                        "description": getattr(product_draft, "description", None),
                        "static":product_draft.static_desc,
                        "category": product_draft.category,
                        "price": str(product_draft.price) if product_draft.price else None,
                        "img_field": product_draft.img_field,
                        "variant": product_draft.variant,
                    },
                    "images": [
                        {
                            "id": media.shopify_media_id,
                            "src": media.src,
                            "alt_text": media.alt_text,
                        } for media in media_drafts
                    ]
                },
                "original": None
            }
            if original_product:
                response["original"] = {
                    "product": {
                        "id": original_product.product_id,
                        "title": original_product.title,
                        "static":product_draft.static_desc,
                        "description": getattr(original_product, "description", None),
                        "category": original_product.category,
                        "price": str(original_product.price) if original_product.price else None,
                        "img_field": original_product.img_field,
                        "variant": original_product.variant,
                    },
                    "images": [
                        {
                            "id": img.shopify_media_id,
                            "src": img.src,
                            "alt_text": img.alt_text,
                        }
                        for img in ProductMedia.objects.filter(product=original_product)
                    ]
                }

            return Response(response, status=200)

        except Exception as e:
            print("Error in get product for optimization:", str(e))
            return Response({"error": str(e)}, status=500)

    def post(self, request, format=None):
        try:
            shopify_store, shopify_token, url = ShopifyAuthMixin().resolve_shopify(request)
            shopify_factory = ShopifyFactoryFunction(
                domain=shopify_store.shop_domain,
                token=shopify_token,
                url=url,
                request=request
            )

            product_id = request.data.get("product_id", [])
            rules = RulesPattern.objects.get(store=shopify_store)

            product, images = shopify_factory.get_product_for_opt(product_id)
            
            product_obj = Product.objects.get(product_id=product['id'])

            product_draft = create_product_draft(product_obj)
            #print('DRAFT CREATED',product['title'])
            #create draft product here
           
            init_ai = AiPromptGenerator(rules,image_data=images,title=product['title'],product_id=product['id'])
            #alt_response = init_ai.generate_alt_text()
            #text_response = init_ai.generate_title()
            #descr, static = init_ai.generate_description()
            
            
            alt_response = [{'id': 'gid://shopify/ProductImage/79160975130999', 'alt': 'Black shoulder support brace workout'}, {'id': 'gid://shopify/ProductImage/79160975065463', 'alt': 'Detailed black shoulder support workout'}, {'id': 'gid://shopify/ProductImage/79160975098231', 'alt': 'Comfortable shoulder support workout'}]
            title_response = [{'product_id': 'gid://shopify/Product/15132834529655', 'title': 'Workout Shoulder Strap for Injury Recovery and Support'}]
            descr = {'product_id': 'gid://shopify/Product/15132834529655', 'description': 'Optimize your workout recovery with our Shoulder Strap for Injury. Designed to provide support and stability, it helps alleviate pain while allowing you to maintain your exercise routine. Perfect for athletes and fitness enthusiasts looking to prevent further injury.'}
            static = False
            print('Optimize please...')
            optimization_body = {
                "titles":title_response,
                "images":alt_response,
                "descriptions":descr['description'],
                "static": static
            }
            optimizer = ProductOptimizer(product_draft,optimization_body)
            results, status_code = optimizer.run()
            # print(results)
            if status_code == 200:
                return Response({"message": results["message"]}, status=200)
            else:
                return Response({"error": results["message"], "details": results["errors"]}, status=500)

        except Exception as e:
            print("Error in optimize_product:", str(e))
            return Response({"error": str(e)}, status=500)


class MerchantApprovalProductOptimization(ShopifyAuthMixin, APIView):
    def post(self, request, format=None):
        try:
            shopify_store, shopify_token, url = ShopifyAuthMixin().resolve_shopify(request)
            shopify_factory = ShopifyFactoryFunction(
                domain=shopify_store.shop_domain,
                token=shopify_token,
                url=url,
                request=request
            )
            print('HERE1')
            request_approval = request.data.get("approval")
            product_id = request.data.get("product")
            print('HERE',product_id)
            product_obj = Product.objects.get(parent_product_id=product_id)
            product_draft = ProductDraft.objects.get(parent_product_id=product_obj.parent_product_id)
            print('sss')
            if not request_approval:
                product_draft.delete()
                return Response({"message": "Merchant declined optimization"}, status=200)

            # ---------------------------------------------------------
            # 1. PRODUCT UPDATE (Title, description, SEO)
            # ---------------------------------------------------------
            product_vars = {
                "input": {
                    "id": product_obj.product_id,
                    "title": product_draft.title,
                    "descriptionHtml": getattr(product_draft, "description", ""),
                    "seo": {
                        "title": product_draft.title,
                        "description": getattr(product_draft, "description", "")
                    }
                }
            }
            print('KNOWW')
            product_resp = shopify_factory.product_update(product_vars)
            product_json = product_resp.json()
            print(product_json)

            product_errors = product_json.get("data", {}).get("productUpdate", {}).get("userErrors", [])
            if product_errors:
                return Response({"error": product_errors}, status=400)

            # ---------------------------------------------------------
            # 2. FILE UPDATE (Image alt text)
            # ---------------------------------------------------------
            media_drafts = ProductMediaDraft.objects.filter(product=product_draft)

            file_payload = []
            for media in media_drafts:
                file_payload.append({
                    "id": media.shopify_media_id,  # gid://shopify/MediaImage/xxx
                    "alt": media.alt_text or ""
                })

            if file_payload:
                file_vars = { "files": file_payload }
                file_resp = shopify_factory.product_image_update(file_vars)
                file_json = file_resp.json()

                file_errors = file_json.get("data", {}).get("fileUpdate", {}).get("userErrors", [])
                if file_errors:
                    return Response({"error": file_errors}, status=400)

            # CLEANUP
            product_draft.delete()
            media_drafts.delete()

            return Response({
                "message": "Product optimization successfully applied",
                "product_update": product_json,
                "media_update": file_json if file_payload else "no media updates"
            }, status=200)

        except Exception as e:
            return Response({"error": str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def import_bulk_products(request):
    """Import products from Shopify in bulk (creates parent product + each variant as its own Product row)."""
    try:
        shopify_domain = request.headers.get('shopify-domain', None)
        if shopify_domain is None:
            return Response({"error": "Domain required from shopify!"}, status=400)

        shopify_token = request.headers['Authorization'].split(' ')[1]
        url = f"https://{shopify_domain}/admin/api/{settings.SHOPIFY_API_VERSION}/graphql.json"
        shopify_factory = ShopifyFactoryFunction(
            shopify_domain, shopify_token, url, request=request
        )

        resp = shopify_factory.get_products({"first": 50, "query": None})
        if resp.status_code != 200:
            return Response({"error": "Failed to fetch products from Shopify", "details": resp.text}, status=502)
        
        product_data = resp.json()
       
        edges = product_data.get("data", {}).get("products", {}).get("edges", [])
        if not edges:
            return Response({"message": "No products found"}, status=200)

        try:
            shopify_store_obj = ShopifyStore.objects.get(shop_domain=shopify_domain)
        except ShopifyStore.DoesNotExist:
            return Response({"error": "Shopify store not found in local DB"}, status=400)

        created = 0
        updated = 0
        with transaction.atomic():
            for edge in edges:
                node = edge.get("node", {})
                gid = node.get("id")
                all_images = []
                parent_images = node.get("images", {}).get("edges", [])
                parent_img_src = None
                if parent_images:
                    parent_img_src = parent_images[0].get("node", {}).get("src")
                if not gid:
                    continue
                title = node.get("title") or ""
                
                # variants and price
                variants_edges = node.get("variants", {}).get("edges", [])
                variant_images = []
                # create/update each variant as its own Product row
                for v_edge in variants_edges:
                    v_node = v_edge.get("node", {})
                    v_gid = v_node.get("id")
                    v_image_obj = v_node.get("image")
                    v_color = v_node.get("color")
                    v_size = v_node.get("size")
                    variant_img_src = None
                    if isinstance(v_image_obj, dict):
                        variant_img_src = v_image_obj.get("src")
                    # fallback to parent image when variant image is not present
                    variant_img = variant_img_src or parent_img_src
                    if not v_gid:
                        continue
                    try:
                        variant_shopify_id = v_gid
                    except Exception:
                        continue
                    variant_images.append(v_image_obj)
                    variant_title = v_node.get("title") or ""
                    # If variant has a descriptive title other than "Default Title" append it
                    full_title = title
                    if variant_title and variant_title.lower() != "default title":
                        full_title = f"{title} - {variant_title}"
                    try:
                        variant_price = Decimal(v_node.get("price")) if v_node.get("price") is not None else None
                    except Exception:
                        variant_price = None

                    variant_sku = v_node.get("sku") or None
                    variant_barcode = v_node.get("barcode") or None
                    print(parent_images)
                    v_obj, v_created = Product.objects.update_or_create(
                        shopify_id=variant_shopify_id,
                        
                        defaults={
                            "product_id": gid,
                            "parent_product_id":gid,
                            "shopify_store": shopify_store_obj,
                            "title": full_title,
                            "sku": variant_sku,
                            "barcode": variant_barcode,
                            "img_field": variant_img,
                            "color": v_color,
                            "size": v_size,
                            "variant": True,
                            "price": variant_price,
                            "synced_with_shopify": True,
                        },
                    )
                    
                    
                    if v_created:
                        for parent_img in parent_images:
                            img_node = parent_img.get("node", {})
                            print(img_node)
                            ProductMedia.objects.update_or_create(
                                shopify_media_id=img_node.get("id"),
                                defaults={
                                    "product": v_obj,
                                    "src": img_node.get("src"),
                                    "shopify_media_id": img_node.get("id"),
                                    "alt_text": img_node.get("altText") or "",
                                }
                            )
                        if v_image_obj:
                            ProductMedia.objects.update_or_create(
                                shopify_media_id=v_image_obj.get("id"),
                                defaults={
                                    "product": v_obj,
                                    "src": v_image_obj.get("src"),
                                    "shopify_media_id": v_image_obj.get("id"),
                                    "alt_text": v_image_obj.get("altText") or "",
                                }
                            )

                        product_score = ProductScore.objects.create(product=v_obj)
                        rules = RulesPattern.objects.get(store=shopify_store_obj)
                        
                        variables = {
                            "product": v_obj,
                            "rules": rules,
                            "product_id": gid,
                            "parent_images": parent_images,
                            "variant_images": variant_images
                        }
                        product_analysis = ProductAnalyzer.analyze_product(variables)

                        if product_analysis:
                            product_score.seo_score = Decimal(product_analysis["seo_score"])
                            product_score.completeness = Decimal(product_analysis["completeness"])
                            product_score.save()
                        created += 1
                    else:
                        updated += 1
            

            custom_user = CustomUser.objects.get(custom_email=shopify_store_obj.email)
            custom_user.shopify_product_import = True
            custom_user.save()

        return Response({"message": "Products imported successfully.", "created": created, "updated": updated}, status=201)

    except Exception as e:
        print("Error in import_bulk_products:", str(e))
        return Response({"error": str(e)}, status=500)
    
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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_webhooks(request):
    """Register webhooks for product events"""
    shopify_domain = request.headers.get('shopify-domain', None)
    shopify_token = None
    if shopify_domain:
        shopify_token = request.headers['Authorization'].split(' ')[1]
    utils = helpers.Utils()
    params = {
        "shopify_token": shopify_token,
        "shopify_domain": shopify_domain,
        "topic":"PRODUCTS_CREATE",
        "url":f"https://{settings.BACKEND}/products/product_webhook"
    }
    
    register_webhooks = utils.webhook_register(params=params)
    print(register_webhooks)
    return Response(register_webhooks["message"], status=register_webhooks["status"])


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