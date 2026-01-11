from celery import shared_task
from django.db import transaction
from products.models import Product, ProductDraft, ProductMedia, ProductMediaDraft, ProductTagDraft, ProductTag
from .models import RulesPattern
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .generatorAi import AiPromptGenerator
from django.conf import settings
from notification.models import Notification
from .wrapperAi import RetrySafeOpenAI
from notification.models import OptimizationJob
from django.utils import timezone
from celery import chain


def notify_user(job, product, status):
    notif_type = "success" if status == "completed" else "error"
    title = "Optimization completed" if status == "completed" else "Optimization failed"
    message = (
        f"Optimization finished for product {product.title}"
        if status == "completed"
        else f"Optimization failed for product {product.title}"
    )

    notification = Notification.objects.create(
        user=job.user,
        notif_type=notif_type,
        title=title,
        message=message,
    )

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_{job.user.id}",
        {
            "type": "job_notification",
            "notification_id": notification.id,
        }
    )


@shared_task
def start_optimization_task(job_id):
    job = OptimizationJob.objects.get(id=job_id)
    print(job_id)
    job.status = "running"
    job.created_at = timezone.now()
    job.save(update_fields=["status", "created_at"])
    product = Product.objects.get(
                product_id=job.product_id
        )
    product_draft, created = ProductDraft.objects.get_or_create(
                    product_id=product.product_id,
                    shopify_store=getattr(product, "shopify_store", None),
                    defaults={
                        "parent_product_id": product.product_id,
                        "title": getattr(product, "title", ""),
                        "description": getattr(product, "description", ""),
                        "optimization_job_id": job_id,
                        "seo_description": getattr(product, "seo_description", ""),
                        "shopify_id": getattr(product, "shopify_id", ""),
                        "img_field": getattr(product, "images", None),
                    },
            )
    chain(
            generate_title_task.si(job_id),
            generate_alt_text_task.si(job_id),
            generate_seo_desc_task.si(job_id),
            generate_description_task.si(job_id),
            finalize_optimization_task.si(job_id),
    ).delay()


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=5, max_retries=3)
def generate_title_task(self, job_id):
    job = OptimizationJob.objects.get(id=job_id)
    product = Product.objects.get(product_id=job.product_id)
    rules = RulesPattern.objects.get(store=job.store)

    generator = AiPromptGenerator(
        rules=rules,
        description=product.description,
        product_id=product.product_id,
    )

    title_response = generator.generate_title()
    title = title_response.get("title")

    draft = ProductDraft.objects.get(
    optimization_job_id=job_id
    )

    draft.apply_title(title)

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=5, max_retries=3)
def generate_description_task(self,job_id):
    job = OptimizationJob.objects.get(id=job_id)
    product = Product.objects.get(product_id=job.product_id)
    rules = RulesPattern.objects.get(store=job.store)

    generator = AiPromptGenerator(
        rules=rules,
        title=product.title,
        product_id=product.product_id,
    )
    descr, static = generator.generate_description()
    draft = ProductDraft.objects.get(
    optimization_job_id=job_id
    )
 
    draft.apply_description(
                descr["description"] if not static else descr,
                static=static
        )

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=5, max_retries=3)
def generate_seo_desc_task(self,job_id):
    job = OptimizationJob.objects.get(id=job_id)
    product = Product.objects.get(product_id=job.product_id)
    rules = RulesPattern.objects.get(store=job.store)
    
    generator = AiPromptGenerator(
        rules=rules,
        seo_desc=product.seo_description,
        product_id=product.product_id,
    )
    draft = ProductDraft.objects.get(
    optimization_job_id=job_id
    )
  
    meta_response = generator.generate_meta_description()
    meta_data = meta_response.get('description')
    draft.apply_seo_description(meta_data)

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=5, max_retries=3)
def generate_alt_text_task(self,job_id):
    job = OptimizationJob.objects.get(id=job_id)
    product = Product.objects.get(product_id=job.product_id)
    product_images = ProductMedia.objects.filter(product=product)
    rules = RulesPattern.objects.get(store=job.store)

    generator = AiPromptGenerator(
        rules=rules,
        image_data=product_images,
        product_id=product.product_id
    )
    if len(product_images) == 0:
        return
    alt_response = generator.generate_alt_text()
    draft = ProductDraft.objects.get(
    optimization_job_id=job_id
        )

    for img in product_images:
        print('IMG',img.shopify_media_id)
        shopify_media_id = getattr(img, "shopify_media_id", None) or getattr(img, "id", None)
        alt_text = getattr(img, "alt", None) or getattr(img, "alt_text", "")
        ProductMediaDraft.objects.update_or_create(
                        product=draft,
                        shopify_media_id=shopify_media_id,
                        defaults={"alt_text": alt_text},
        )
    apply_alt_text_updates(draft, alt_response)

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=5, max_retries=3)
def finalize_optimization_task(self,job_id):
    job = OptimizationJob.objects.get(id=job_id)
    product = Product.objects.get(product_id=job.product_id)

    job.status = "completed"
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "finished_at"])

    product.optimization_status = "completed"
    product.optimized = False
    product.save(update_fields=["optimization_status"])

    notify_user(job, product, "completed")



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