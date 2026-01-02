from celery import shared_task
from django.db import transaction
from products.models import Product, ProductDraft, ProductMedia, ProductMediaDraft, ProductTagDraft, ProductTag
from .models import RulesPattern
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .generatorAi import AiPromptGenerator
from .wrapperAi import RetrySafeOpenAI
from notification.models import OptimizationJob
from django.utils import timezone


def notify_user(job,product, status):
    channel_layer = get_channel_layer()

    async_to_sync(channel_layer.group_send)(
        f"user_{job.user.id}",
        {
            "type": "job_notification",
            "event": "OPTIMIZATION_DONE" if status == "completed" else "OPTIMIZATION_FAILED",
            "job_id": str(job.id),
            "product_id": product.id,
        }
    )


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=30,
    retry_jitter=True,
    max_retries=3
)
def optimize_product_task(self, job_id):
    """
    Orchestrates full product optimization safely.
    """
    try:
        with transaction.atomic():
            job = OptimizationJob.objects.select_related("user").get(id=job_id)
            job.status = "running"
            job.save(update_fields=["status"])

            product = Product.objects.get(
                product_id=job.product_id
            )
            print('FOUND PRODUCT:', product.title)
            product_images = ProductMedia.objects.filter(product=product)
            product_tag = ProductTag.objects.filter(product=product)
            print('OPTIMIZING PRODUCT:', product.title)

            rules = RulesPattern.objects.get(store=job.store)
            product_draft, created = ProductDraft.objects.get_or_create(
                product_id=product.product_id,
                shopify_store=getattr(product, "shopify_store", None),
                defaults={
                    "parent_product_id": product.product_id,
                    "title": getattr(product, "title", ""),
                    "description": getattr(product, "description", ""),
                    "seo_description": getattr(product, "seo_description", ""),
                    "shopify_id": getattr(product, "shopify_id", ""),
                    "img_field": getattr(product, "images", None),
                },
            )
            
            job.product_draft = product_draft
            job.save(update_fields=["product_draft"])

            for img in product_images:
                shopify_media_id = getattr(img, "shopify_media_id", None) or getattr(img, "id", None)
                alt_text = getattr(img, "alt", None) or getattr(img, "alt_text", "")
                ProductMediaDraft.objects.update_or_create(
                    product=product_draft,
                    shopify_media_id=shopify_media_id,
                    defaults={"alt_text": alt_text},
                )
            for tag in product_tag:
                tag_name = getattr(tag, "tag_name", None) or getattr(tag, "name", None) or ""
                ProductTagDraft.objects.update_or_create(
                    product=product_draft,
                    tag_name=tag_name,
                )

            generator = AiPromptGenerator(
                rules=rules,
                image_data=product_images,
                description=product.description,
                seo_desc=product.seo_description,
                title=product.title,
                product_id=product.product_id
            )

            # --- Title ---
            title_response = generator.generate_title()
            title = title_response.get('title')
            print('title response',title)
            product_draft.apply_title(title)
            print('TITLE UPDATED')
            # --- Images ---
            alt_response = generator.generate_alt_text()
            print('alt response',alt_response)
            apply_alt_text_updates(product_draft, alt_response)
            print('IMAGES UPDATED')
            # --- Meta description ---
            meta_response = generator.generate_meta_description()
            meta_data = meta_response.get('description')
            product_draft.apply_seo_description(meta_data)
            print('META DESCRIPTION UPDATED')
            # --- Description ---
            descr, static = generator.generate_description()
            
            product_draft.apply_description(
                descr["description"] if not static else descr,
                static=static
            )
            job.status = "completed"
            job.finished_at = timezone.now()
            job.save(update_fields=["status", "finished_at"])
            product.optimization_status = "completed"
            product.optimized = True
            product.save(update_fields=["optimization_status"])
            notify_user(job,product, "completed")

            # product_draft.mark_completed()

        
    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        job.save(update_fields=["status", "error"])
        notify_user(job, product,"failed")
        raise

def apply_alt_text_updates(product_draft, alt_payload):
        """
        alt_payload example:
        [
            {"id": "gid://shopify/MediaImage/123", "alt": "Black shoulder brace"},
            ...
        ]
        """
        media_map = {
            m.shopify_media_id: m
            for m in ProductMediaDraft.objects.filter(product=product_draft)
        }

        for item in alt_payload:
            media_id = item.get("id")
            alt = item.get("alt", "").strip()

            media = media_map.get(media_id)
            if not media:
                continue  # ignore unknown media safely

            media.alt_text = alt
            media.save(update_fields=["alt_text"])