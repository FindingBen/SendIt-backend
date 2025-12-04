import json
import logging
from .models import ProductDraft, ProductMediaDraft
from django.db import transaction
from .models import ProductDraft


logger = logging.getLogger(__name__)

class ProductOptimizer:
    def __init__(self, product_draft: ProductDraft,images=None, titles=None, descriptions=None, categories=None):
        self.product_draft = product_draft
        self.images = images
        self.titles = titles
        self.descriptions = descriptions
        self.categories = categories

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
            


    def optimize_image_alt_text(self):
        changed = []

        for image in self.images:
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
        new_title = self.titles

        self.product_draft.title = new_title
        self.product_draft.save()

        msg = f"Generated new title: {new_title}"
        logger.info(msg)

        self.results["changed_fields"]["title"] = changed


    def optimize_product_description(self):
        pass

    def optimize_product_category(self):
        pass
        
    