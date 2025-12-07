import json
import logging
from .models import ProductDraft, ProductMediaDraft
from django.db import transaction
from .models import ProductDraft


logger = logging.getLogger(__name__)

class ProductOptimizer:
    def __init__(self, product_draft: ProductDraft,request_body):
        self.product_draft = product_draft
        self.images = request_body['images']
        self.titles = request_body['titles']
        self.descriptions = request_body['descriptions']
        self.seo_desc = request_body['seo_desc']
        self.static = request_body['static']

        self.results = {
            "status": "pending",
            "message": "",
            "changed_fields": {},
            "errors": [],
        }


    def run(self):
        """
        main entrypoint for optimizer
        """
        try:
            # Always create/update draft
            draft = self.product_draft
            self.results["draft_product_id"] = draft.shopify_id

            # Run modules
            if self.images:
                self.optimize_image_alt_text()
            
            if self.titles:
                self.optimize_product_title()

            if self.descriptions:
                self.optimize_descritpion()

            if self.seo_desc:
                self.optimize_meta_description()
            # other optimizers coming soon...
            # if self.titles: self.optimize_product_title()
            # if self.descriptions: self.optimize_product_description()

            self.results["status"] = "success"
            self.results["message"] = "Optimization completed"
            return self.results, 200

        except Exception as e:
            self.results["status"] = "error"
            self.results["message"] = "Optimization failed"
            self.results["errors"].append(str(e))
            return self.results, 500
            
    def optimize_descritpion(self):
        changed = []
        
       
        new_desc = self.descriptions

        self.product_draft.description = new_desc
        self.product_draft.static_desc = self.static
        self.product_draft.save()

        msg = f"Generated new desc: {new_desc}"
        logger.info(msg)

        self.results["changed_fields"]["description"] = changed

    def optimize_image_alt_text(self):
        changed = []

        for image in self.images:
            print('IMM',image)
            draft_media, created = ProductMediaDraft.objects.update_or_create(
                shopify_media_id=image["id"],
                defaults={
                    "product": self.product_draft,
                    "src": image.get("src"),
                    "alt_text": image.get("alt"),
                }
            )

            changed.append({
                "image_id": image["id"],
                "alt_text": draft_media.alt_text,
                "created": created,
            })

        self.results["changed_fields"]["images"] = changed


    def optimize_product_title(self):
        changed = []
        for title_obj in self.titles:
            print(title_obj)
            new_title = title_obj['title']

        self.product_draft.title = new_title
        self.product_draft.save()

        msg = f"Generated new title: {new_title}"
        logger.info(msg)

        self.results["changed_fields"]["title"] = changed

    def optimize_meta_description(self):
        changed = []
       
        new_seo_desc = self.seo_desc

        self.product_draft.seo_description = new_seo_desc
        self.product_draft.save()

        msg = f"Generated new desc: {new_seo_desc}"
        logger.info(msg)

        self.results["changed_fields"]["meta description"] = changed
        
    