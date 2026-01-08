from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from backend import settings
from django.http import HttpResponse
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .models import Product,ShopifyWebhookLog, RulesPattern, ProductTag,ProductTagDraft,ProductVariant,ProductVariantDraft,ProductDraft,ProductMediaDraft,ProductScore, ProductMedia
from decimal import Decimal
from typing import Optional, Dict, Any
from django.db import transaction
from base.models import ShopifyStore, CustomUser
from base.utils import helpers
from .tasks import optimize_product_task
from base.analyzers import Prompting
from base.auth import get_business_info, OpenAiAuthInit
from base.shopify_functions import ShopifyFactoryFunction
from base.queries import GET_ALL_PRODUCTS,UPDATE_PRODUCT_VARIANTS_BULK,CREATE_WEBHOOK
from .serializers import ProductSerializer,RulesetSerializer
from .analyzers import ProductAnalyzer
from .generatorAi import AiPromptGenerator
from .optimizers import ProductOptimizer
from .helpers import create_product_draft, generate_unique_barcode, generate_unique_sku
import json
from notification.models import OptimizationJob



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
            ruleset = RulesPattern.objects.filter(store=shopify_store).first()
            serializer = RulesetSerializer(ruleset)

            return Response({"ruleset":serializer.data}, status=200)
        except Exception as e:
            return Response({"error": "Exception during analysis", "details": str(e)}, status=500)
        
    def post(self, request, format=None):
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

    def patch(self, request, format=None):
        """
        Partial update of RulesPattern
        """
        try:
            shopify_store, _, _ = self.resolve_shopify(request)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)

        ruleset = RulesPattern.objects.filter(store=shopify_store).first()
        if not ruleset:
            return Response(
                {"error": "Ruleset does not exist"},
                status=404,
            )

        data = request.data

        allowed_fields = {
            "product_name_rule",
            "product_description_rule",
            "product_image_rule",
            "product_variant_rule",
            "product_tag_rule",
            "product_alt_image_rule",
            "keywords"
        }

        updated_fields = []

        for field, value in data.items():
            if field in allowed_fields:
                setattr(ruleset, field, value)
                updated_fields.append(field)

        if not updated_fields:
            return Response(
                {"error": "No valid fields provided for update"},
                status=400,
            )

        ruleset.save(update_fields=updated_fields)

        return Response(
            {
                "message": "Rules updated successfully",
                "updated_fields": updated_fields,
            },
            status=200,
        )


class ProductOptimizeView(ShopifyAuthMixin, APIView):

    def get(self, request, format=None):
        try:
            shopify_store, shopify_token, url = ShopifyAuthMixin().resolve_shopify(request)
            product_id = request.query_params.get("product_id")
            product = Product.objects.get(product_id=product_id)
  
            product_draft = ProductDraft.objects.get(parent_product_id=product_id)
            if not product_draft:
                return Response({"error": "Draft for this product does not exist"}, status=404)
            
            media_drafts = ProductMediaDraft.objects.filter(product=product_draft)
            # jobs = OptimizationJob.objects.get(id=product_draft.optimization_job_id)
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
            
            return Response({"message": "Optimization started. Check back later for results."}, status=202)

        except Exception as e:
            print("Error in optimize_product:", str(e))
            return Response({"error": str(e)}, status=500)


class MerchantApprovalProductOptimization(ShopifyAuthMixin, APIView):
    def post(self, request, format=None):
        try:
            with transaction.atomic():
                shopify_store, shopify_token, url = ShopifyAuthMixin().resolve_shopify(request)
                shopify_factory = ShopifyFactoryFunction(
                    domain=shopify_store.shop_domain,
                    token=shopify_token,
                    url=url,
                    request=request
                )

                request_approval = request.data.get("approval")
                product_id = request.data.get("product")
                changes = request.data.get('approved_changes')
                if isinstance(changes, str):
                    # accept comma-separated string as well
                    changes = [c.strip() for c in changes.split(",") if c.strip()]
                print('PRODUCT ID',changes)
                product_obj = Product.objects.get(parent_product_id=product_id)
                try:
                    product_draft = ProductDraft.objects.get(parent_product_id=product_obj.parent_product_id)
                except ProductDraft.DoesNotExist:
                    return Response({"error": "Can't approve changes because they don't exist!"}, status=404)

                if not request_approval:
                    product_draft.delete()
                    product_obj.optimization_status = "not started"
                    product_obj.save(update_fields=["optimization_status"])
                    return Response({"message": "Merchant declined optimization"}, status=200)

                product_vars = {"input": {"id": product_obj.product_id}}
                input_payload = product_vars["input"]

                if "title" in changes:
                    input_payload["title"] = product_draft.title
                if "description" in changes or "descriptionHtml" in changes:
                    # prefer "description" key from draft
                    input_payload["descriptionHtml"] = getattr(product_draft, "description", "")
                if "seo" in changes:
                    input_payload["seo"] = {
                        "title": product_draft.title,
                        "description": getattr(product_draft, "seo_description", "")
                    }
                product_json = None
                product_errors = []
                # only call Shopify product_update when there are fields besides id
                if len(input_payload.keys()) > 1:
                    product_resp = shopify_factory.product_update(product_vars)
                    product_json = product_resp.json()
                    product_errors = product_json.get("data", {}).get("productUpdate", {}).get("userErrors", [])
                    if product_errors:
                        return Response({"error": product_errors}, status=400)
                
                file_json = None
                media_drafts = ProductMediaDraft.objects.filter(product=product_draft)
                print('media draft', media_drafts)
                if "alt_text" in changes and media_drafts.exists():
                    file_payload = []
                    print('CHANGE ALT TEXT')
                    for media in media_drafts:
                        print('MEDIA',media)
                        
                        file_payload.append({
                                "id": media.shopify_media_id,
                                "alt": media.alt_text or ""
                            })
                    file_payload = [f for f in file_payload if "MediaImage" in f["id"]]
                    print('FILE PAYLOAD',file_payload)
                    if file_payload:
                        file_vars = {"files": file_payload}
                        file_resp = shopify_factory.product_image_update(file_vars)
                        file_json = file_resp.json()
                        print('FILE JSON',file_json)
                        file_errors = file_json.get("data", {}).get("fileUpdate", {}).get("userErrors", [])
                        if file_errors:
                            return Response({"error": file_errors}, status=400)

                        # apply alt text updates to local ProductMedia rows
                        try:
                            for md in media_drafts:
                                ProductMedia.objects.filter(
                                    shopify_media_id=md.shopify_media_id,
                                    product=product_obj
                                ).update(alt_text=md.alt_text or "", field_id=getattr(md, "field_id", None))
                        except Exception as e:
                            print("Failed to update local ProductMedia alt_texts:", str(e))

                # apply approved draft fields to local Product immediately
                update_fields = []
                try:
                    if "title" in changes:
                        product_obj.title = product_draft.title
                        update_fields.append("title")
                    if "description" in changes or "descriptionHtml" in changes:
                        product_obj.description = getattr(product_draft, "description", "")
                        update_fields.append("description")
                    if "seo" in changes:
                        product_obj.seo_description = getattr(product_draft, "seo_description", "")
                        update_fields.append("seo_description")
                    if getattr(product_draft, "img_field", None) and "img_field" in changes:
                        product_obj.img_field = product_draft.img_field
                        update_fields.append("img_field")
                    if update_fields:
                        product_obj.save(update_fields=update_fields)
                except Exception as e:
                    print("Failed to apply draft to local Product:", str(e))

                # cleanup draft records
                product_score = ProductScore.objects.get(product=product_obj)
                rules = RulesPattern.objects.filter(store=shopify_store).first()
                variables = {
                            "product": product_obj,
                            "rules": rules,
                            "product_id": product_obj.shopify_id,
                            "parent_images": media_drafts,
                            "variant_images": [],  # analyzer can inspect ProductVariant if needed
                }
                analysis = ProductAnalyzer.analyze_product(variables)
                if analysis:
                    product_score.seo_score = Decimal(analysis.get("seo_score", 0))
                    product_score.completeness = Decimal(analysis.get("completeness", 0))
                    product_score.save()
                product_obj.optimization_status = "not started"
                product_obj.optimized = True
                product_obj.save(update_fields=["optimization_status","optimized"])
                product_draft.delete()
                media_drafts.delete()

                return Response({
                    "message": "Product optimization successfully applied",
                    "product_update": product_json,
                    "media_update": file_json if file_json else "no media updates"
                }, status=200)
                # # ---------------------------------------------------------
                # # 1. PRODUCT UPDATE (Title, description, SEO)
                # # ---------------------------------------------------------
                # product_vars = {
                #     "input": {
                #         "id": product_obj.product_id,
                #         "title": product_draft.title,
                #         "descriptionHtml": getattr(product_draft, "description", ""),
                #         "seo": {
                #             "title": product_draft.title,
                #             "description": product_draft.seo_description
                #         }
                #     }
                # }
                # product_resp = shopify_factory.product_update(product_vars)
                # product_json = product_resp.json()

                # product_errors = product_json.get("data", {}).get("productUpdate", {}).get("userErrors", [])
                # if product_errors:
                #     return Response({"error": product_errors}, status=400)
                
                # try:
                #     product_obj.title = product_draft.title
                #     product_obj.description = getattr(product_draft, "description", "")
                #     product_obj.seo_description = getattr(product_draft, "seo_description", "")
                    
                #     product_obj.save(update_fields=["title", "description", "seo_description"])
                # except Exception as e:
                #     print("Failed to apply draft to local Product:", str(e))
                
                # media_drafts = ProductMediaDraft.objects.filter(product=product_draft)

                # file_payload = []
                # for media in media_drafts:
                #     # Only send payload if ImageSource ID exists
                #     if media.field_id:
                #         file_payload.append({
                #             "id": media.shopify_media_id,     # ✔ correct
                #             "alt": media.alt_text or ""
                #         })
                # file_payload = [f for f in file_payload if "MediaImage" in f["id"]]
                # if file_payload:
                #     file_vars = { "files": file_payload }
                #     file_resp = shopify_factory.product_image_update(file_vars)
                #     file_json = file_resp.json()

                #     file_errors = file_json.get("data", {}).get("fileUpdate", {}).get("userErrors", [])
                #     if file_errors:
                #         return Response({"error": file_errors}, status=400)

                # # CLEANUP
                # product_score = ProductScore.objects.get(product=product_obj)
                # rules = RulesPattern.objects.filter(store=shopify_store).first()
                # variables = {
                #             "product": product_obj,
                #             "rules": rules,
                #             "product_id": product_obj.shopify_id,
                #             "parent_images": media_drafts,
                #             "variant_images": [],  # analyzer can inspect ProductVariant if needed
                # }
                # analysis = ProductAnalyzer.analyze_product(variables)
                # if analysis:
                #     product_score.seo_score = Decimal(analysis.get("seo_score", 0))
                #     product_score.completeness = Decimal(analysis.get("completeness", 0))
                #     product_score.save()
                # product_obj.optimization_status = "not started"
                # product_obj.save(update_fields=["optimization_status"])
                # product_draft.delete()
                # media_drafts.delete()

                # return Response({
                #     "message": "Product optimization successfully applied",
                #     "product_update": 'ss',
                #     #"media_update": file_json if file_payload else "no media updates"
                # }, status=200)

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
        print("SSENAAA",product_data)
        edges = product_data.get("data", {}).get("products", {}).get("edges", [])
        if not edges:
            return Response({"message": "No products found"}, status=200)

        try:
            shopify_store_obj = ShopifyStore.objects.get(shop_domain=shopify_domain)
        except ShopifyStore.DoesNotExist:
            return Response({"error": "Shopify store not found in local DB"}, status=400)

        created = 0
        updated = 0
        # ...existing code...
        with transaction.atomic():
            for edge in edges:
                node = edge.get("node", {})
                gid = node.get("id")
                seo_title = node.get("seo", {}).get("title", None)
                tags = node.get('tags',[])
                
                seo_meta = node.get("seo", {}).get("description", None)
                if not gid:
                    continue

                title = node.get("title") or ""

                # ---------------------------------------------------------------------
                # EXTRACT MEDIA IMAGES (media edges -> list of media dicts)
                # ---------------------------------------------------------------------
                parent_images_raw = node.get("media", {}).get("edges", []) or []
                parent_images = []
                for img_edge in parent_images_raw:
                    media_node = img_edge.get("node")
                    if not media_node:
                        continue
                    image_obj = media_node.get("image", {}) or {}
                    parent_images.append({
                        "media_id": media_node.get("id"),      # MediaImage ID (gid)
                        "file_id": image_obj.get("id"),        # ImageSource ID (gid)
                        "url": image_obj.get("url"),
                        "alt": image_obj.get("altText") or "",
                    })

                # Parent fallback image (src)
                parent_img_src = parent_images[0]["url"] if parent_images else None

                # ---------------------------------------------------------------------
                # DETERMINE VARIANT STATE
                # ---------------------------------------------------------------------
                variants_edges = node.get("variants", {}).get("edges", []) or []
                variants_count = node.get("variantsCount", {}).get("count", 0)

                has_variants = False
                if variants_count and int(variants_count) > 1:
                    has_variants = True
                elif len(variants_edges) > 1:
                    has_variants = True
                else:
                    # single variant: check its title for "Default Title"
                    v0 = variants_edges[0].get("node") if variants_edges else {}
                    v0_title = (v0.get("title") or "").strip().lower() if v0 else ""
                    if v0_title and v0_title != "default title":
                        has_variants = True

                # ---------------------------------------------------------------------
                # CREATE / UPDATE PARENT PRODUCT
                # ---------------------------------------------------------------------
                parent_defaults = {
                    "product_id": gid,
                    "parent_product_id": gid,
                    "shopify_store": shopify_store_obj,
                    "title": title,
                    "description": node.get("descriptionHtml") or "",
                    "seo_description": seo_meta,
                    "img_field": parent_img_src,
                    "variant": bool(has_variants),
                    "synced_with_shopify": True,
                }

                parent_obj, parent_created = Product.objects.update_or_create(
                    shopify_id=gid,
                    defaults=parent_defaults,
                )
                if parent_created:
                    for tag in tags:
                        tag_obj, created = ProductTag.objects.get_or_create(
                            product=parent_obj,
                            tag_name=tag
                        )
                # ---------------------------------------------------------------------
                # CREATE/UPDATE PRODUCT MEDIA (attach to parent product)
                # ---------------------------------------------------------------------
                for media in parent_images:
                    try:
                        ProductMedia.objects.update_or_create(
                            shopify_media_id=media["media_id"],
                            defaults={
                                "product": parent_obj,
                                "field_id": media["file_id"],
                                "src": media["url"],
                                "alt_text": media["alt"] or "",
                            },
                        )
                    except Exception as e:
                        # Log the failure and continue with other media
                        print("Failed to upsert ProductMedia", media.get("media_id"), str(e))

                # ---------------------------------------------------------------------
                # CREATE VARIANTS OR APPLY SINGLE VARIANT TO PARENT
                # ---------------------------------------------------------------------
                # Track whether we created or updated any variant rows for metrics
                for v_edge in variants_edges:
                    v_node = v_edge.get("node", {}) or {}
                    v_gid = v_node.get("id")
                    if not v_gid:
                        continue

                    v_title = (v_node.get("title") or "").strip()
                    v_image = v_node.get("image") or {}
                    variant_img_src = v_image.get("url") if isinstance(v_image, dict) else None
                    img_src_to_use = variant_img_src or parent_img_src

                    try:
                        variant_price = Decimal(v_node.get("price")) if v_node.get("price") else None
                    except Exception:
                        variant_price = None

                    # Case A: product has no real variants -> store variant fields on parent product
                    if not has_variants and (v_title.lower() == "default title" or v_title == ""):
                        updated_fields = {}
                        if v_node.get("sku"):
                            parent_obj.sku = v_node.get("sku")
                            updated_fields["sku"] = v_node.get("sku")
                        if v_node.get("barcode"):
                            parent_obj.barcode = v_node.get("barcode")
                            updated_fields["barcode"] = v_node.get("barcode")
                        if variant_price is not None:
                            parent_obj.price = variant_price
                            updated_fields["price"] = variant_price
                        # ensure parent is marked synced
                        parent_obj.synced_with_shopify = True
                        save_fields = list(updated_fields.keys()) + ["synced_with_shopify"]
                        try:
                            parent_obj.save(update_fields=save_fields if save_fields else None)
                            if parent_created:
                                created += 1
                            else:
                                updated += 1
                        except Exception as e:
                            print("Failed to update parent product with implicit variant data:", str(e))
                    else:
                        # Case B: real variant(s) exist -> create/update ProductVariant rows
                        pv_defaults = {
                            "sku": v_node.get("sku"),
                            "barcode": v_node.get("barcode"),
                            "img_field": img_src_to_use,
                        }
                        # Use name (title) as identifying attribute for update_or_create
                        pv_name = v_title if v_title and v_title.lower() != "default title" else v_gid
                        pv_list = []
                        try:
                            pv_obj, pv_created = ProductVariant.objects.update_or_create(
                                parent_product=parent_obj,
                                name=pv_name,
                                defaults=pv_defaults,
                            )

                            if pv_created:
                                pv_list.append(pv_obj)
                                created += 1
                            else:
                                updated += 1
                        except Exception as e:
                            print("Failed to create/update ProductVariant for", v_gid, str(e))
                            continue

                # Optionally create analysis/score for newly created parent
                if parent_created:
                    try:
                        medias = ProductMedia.objects.filter(product=parent_obj)
                        product_score = ProductScore.objects.create(product=parent_obj)
                        rules = RulesPattern.objects.filter(store=shopify_store_obj).first()
                        variables = {
                            "product": parent_obj,
                            "rules": rules,
                            "product_id": gid,
                            "parent_images": medias,
                            "variant_images": [],  # analyzer can inspect ProductVariant if needed
                        }
                        analysis = ProductAnalyzer.analyze_product(variables)
                        if analysis:
                            product_score.seo_score = Decimal(analysis.get("seo_score", 0))
                            product_score.completeness = Decimal(analysis.get("completeness", 0))
                            product_score.save()
                    except Exception as e:
                        print("Product analysis failed for", gid, str(e))

            custom_user = CustomUser.objects.get(custom_email=shopify_store_obj.email)
            custom_user.shopify_product_import = True
            custom_user.save()

        return Response({"message": "Products imported successfully.", "created": created, "updated": updated}, status=201)

    except Exception as e:
        print("Error in import_bulk_products:", str(e))
        return Response({"error": str(e)}, status=500)
    
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
        "topic":"PRODUCTS_UPDATE",
        "url":f"https://{settings.BACKEND}/products/update_product_webhook"
    }
    
    register_webhooks = utils.webhook_register(params=params)
    print(register_webhooks)
    return Response(register_webhooks["message"], status=register_webhooks["status"])
