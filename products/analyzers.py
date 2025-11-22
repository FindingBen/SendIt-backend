import json
from .models import Product, ProductScore


class ProductAnalyzer:
    @staticmethod
    def analyze_product(product_data):
        """
        Analyzes the product data and returns a score based on completeness and SEO factors.
        :param product_data: dict containing product information
        :return: dict with analysis results
        """
        score = 0.0
        completeness = 0.0
        total_fields = 5  # Example fields to check: title, description, images, variants, tags
        filled_fields = 0

        # Check for title
        if product_data.get('title'):
            filled_fields += 1
            score += 10.0  # Example scoring

        # Check for description
        if product_data.get('description'):
            filled_fields += 1
            score += 20.0

        # Check for images
        if product_data.get('images'):
            filled_fields += 1
            score += 30.0

        # Check for variants
        if product_data.get('variants'):
            filled_fields += 1
            score += 20.0

        # Check for tags
        if product_data.get('tags'):
            filled_fields += 1
            score += 20.0

        completeness = (filled_fields / total_fields) * 100.0

        return {
            'seo_score': round(score, 2),
            'completeness': round(completeness, 2)
        }