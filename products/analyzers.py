import json
from .models import Product, ProductScore, RulesPattern, ProductMedia, ProductTag
from base.shopify_functions import ShopifyFactoryFunction

class ProductAnalyzer:

    @staticmethod
    def analyze_product(variables: dict):

        product = variables["product"]
        rules = variables["rules"]
        parent_images = variables["parent_images"]
        variant_images = variables["variant_images"]

        seo_score = 0
        completeness = 0
        print(variables)
        #
        # TITLE
        #
        title = product.title or ""
        if rules.min_title_length <= len(title) <= rules.max_title_length:
            seo_score += 15

        if len(title) > 0:
            completeness += 20

        ### Seo description
        seo_desc = product.seo_description or ""
        if 20 <= len(seo_desc) <= 160:
            seo_score += 15

        tags = ProductTag.objects.filter(product=product)

        if len(tags) > 0:
            completeness += 10


        #
        # DESCRIPTION
        #
        description = getattr(product, "description", "")
        if description:
            completeness += 25
            if rules.min_description_length <= len(description) <= rules.max_description_length:
                seo_score += 20

        #
        # IMAGE SCORING
        #

        image_results = ProductAnalyzer.analyze_images(
            parent_images, variant_images, rules
        )
        total_score = image_results
        seo_score += image_results["seo_score"]
        completeness += image_results["completeness"]

        #
        # NORMALIZE
        #
        seo_score = min(seo_score, 100)
        completeness = min(completeness, 100)

        return {
            "seo_score": round(seo_score, 2),
            "completeness": round(completeness, 2),
        }


    @staticmethod
    def analyze_image(image, rules):

        alt = image.alt_text

        seo_score = 0
        completeness = 0

        # check alt text
        seo_score = 0.0
        completeness = 0.0

        if alt:
            # give base points for having alt text
            completeness += 5.0
            seo_score += 5.0

            # reward longer descriptive alt text up to a cap
            # use words count between 3..20 as ideal
            word_count = len(alt.split())
            if 3 <= word_count <= 20:
                seo_score += 2.5
                completeness += 2.5
            else:
                # partial based on length (clamped)
                wc = min(word_count, 20)
                completeness += 2.5 * (wc / 20.0)
                seo_score += 2.5 * (wc / 20.0)

            # optional: keyword relevance from rules.keywords (if present)
            keywords = getattr(rules, "keywords", []) or []
            for kw in keywords:
                if kw and kw.lower() in alt.lower():
                    seo_score += 2.5
                    break
        else:
            # small penalty if missing
            completeness += 0.0
            seo_score += 0.0

        return {
            "seo_score": max(seo_score, 0.0),
            "completeness": max(completeness, 0.0),
            "alt_text": alt,
        }


    @staticmethod
    def analyze_images(parent_images, variant_images, rules):
        total_seo = 0
        total_completeness = 0
        image_count = 0

        # all_images = (parent_images or []) + (variant_images or [])
        if isinstance(parent_images,list):
            image_count = len(parent_images)
            if image_count == 0:
                return {"seo_score": 0.0, "completeness": 0.0}
        
        elif parent_images is None:
            return {"seo_score": 0.0, "completeness": 0.0}

        total_seo = 0.0
        total_completeness = 0.0
        for img in parent_images:
            image_count += 1
            img_result = ProductAnalyzer.analyze_image(img, rules)
            print('IMAGE_RESULT', img_result)
            total_seo += img_result["seo_score"]
            total_completeness += img_result["completeness"]

        avg_seo = total_seo / image_count
        avg_completeness = total_completeness / image_count

        seo_contribution = min(avg_seo, 20.0)
        completeness_contribution = min(avg_completeness, 20.0)

        return {
            "seo_score": round(seo_contribution, 2),
            "completeness": round(completeness_contribution, 2),
        }
