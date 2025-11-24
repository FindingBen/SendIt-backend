import json
from .models import Product, ProductScore, RulesPattern
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
        alt = (
            getattr(image, "alt", None)
            or getattr(image, "altText", None)
            or (image.get("alt") if isinstance(image, dict) else None)
            or (image.get("altText") if isinstance(image, dict) else None)
        )

        seo_score = 0
        completeness = 0

        # image is present
        completeness += 20

        # check alt text
        if alt and len(alt.strip()) > 0:
            completeness += 10
            seo_score += 10

            # recommended alt text length: 5–20 words
            word_count = len(alt.split())
            if 5 <= word_count <= 20:
                seo_score += 5

            # keyword relevance
            keywords = getattr(rules, "keywords", [])
            for kw in keywords:
                if kw.lower() in alt.lower():
                    seo_score += 5
                    break

        else:
            completeness -= 5
            seo_score -= 5

        return {
            "seo_score": max(seo_score, 0),
            "completeness": max(completeness, 0),
            "alt_text": alt or "",
        }


    @staticmethod
    def analyze_images(parent_images, variant_images, rules):
        total_seo = 0
        total_completeness = 0
        image_count = 0

        all_images = (parent_images or []) + (variant_images or [])

        for img in all_images:
            img_result = ProductAnalyzer.analyze_image(img, rules)
            total_seo += img_result["seo_score"]
            total_completeness += img_result["completeness"]
            image_count += 1

        if image_count == 0:
            return { "seo_score": 0, "completeness": 0 }

        return {
            "seo_score": round(total_seo / image_count, 2),
            "completeness": round(total_completeness / image_count, 2),
        }
