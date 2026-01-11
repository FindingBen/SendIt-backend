import json
import re
from openai import OpenAI
from base.auth import OpenAiAuthInit
from .wrapperAi import RetrySafeOpenAI


class AiPromptGenerator:
    def __init__(self, rules, product_id,image_data=None,title=None,description=None,seo_desc = None):
        self.openai = RetrySafeOpenAI()
        self.rules = rules
        self.image_data = image_data
        self.title = title
        self.product_id = product_id
        self.description = description
        self.seo_desc = seo_desc


    def generate_title(self):
        prompt = f"""
        You are an expert Shopify SEO title optimizer.

        Generate ONE optimized product title based on:
        - Original title: "{self.title}"
        - Keywords: {self.rules.keywords}
        - Title rules: {self.rules.product_name_rule}
        - Length: {self.rules.min_title_length}–{self.rules.max_title_length} characters

        Rules:
        - Generate EXACTLY ONE title
        - Do NOT provide multiple options
        - Do NOT include explanations
        - Output ONLY valid JSON

        Return EXACTLY this object:
        {{
        "product_id": "{self.product_id}",
        "title": "<optimized title>"
        }}
        """


        response = self.openai.chat_completion(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Return ONLY valid JSON. No markdown. No code fences."},
                {"role": "user", "content": prompt},
            ]
        )
        raw = response.choices[0].message.content
        print("RAW TITLE OUTPUT:", raw)

        # Extract + validate JSON
        new_title = self.extract_json(raw)
        return new_title

    def generate_alt_text(self):
        """
        Generates optimized alt text for ALL product images at once.
        Returns a list of objects: [{"id": "...", "alt": "..."}]
        """


        # First classify all images
        image_info = self.classify_images(self.image_data)
        print('CLASSIFYING')
        # Prepare prompt
        prompt = f"""
        You are an expert Shopify SEO image optimizer.
        Generate ALTERNATIVE TEXT for EACH image separately.

        Follow these rules:
        - Use the image description + detected objects/colors
        - Include relevant keywords: {self.rules.keywords}
        - Recommended length: 5–20 words
        - {self.rules.product_alt_image_rule}
        - Max length: {self.rules.max_alt_desc_length} characters
        - Alt text MUST describe what is visually in the image
        - Do NOT output explanations. Output ONLY pure JSON.

        Input image analysis:
        {json.dumps(image_info, indent=2)}

        Return a JSON array where EACH element is:
        {{
        "id": "<image_gid>",
        "alt": "<generated alt text>"
        }}
        """

        response = self.openai.chat_completion(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Return ONLY valid JSON. No markdown. No code fences."},
                {"role": "user", "content": prompt},
            ]
        )

        raw = response.choices[0].message.content
        print("RAW ALT OUTPUT:", raw)

        # Extract + validate JSON
        alt_list = self.extract_json(raw)

        # Final validation: ensure list of {id, alt}
        final = []
        for img in alt_list:
            if "id" in img and "alt" in img:
                final.append({"id": img["id"], "alt": img["alt"].strip()})

        return final

    def generate_description(self):
        template = self.rules.product_description_template
        static = False
        if template and template.strip():
            static = True
            return template, static
        
        prompt = f"""
        Generate a product description following these rules:

        - SEO best practices
        - Length between {self.rules.min_description_length} and {self.rules.max_description_length} characters
        - Description rules: {self.rules.product_description_rule}
        - Use keywords: {self.rules.keywords or "None"}
        - The product title is: "{self.title}"

        Return a JSON object where description is:
        {{
        "product_id": "{self.product_id}",
        "description": "<generated/modified description>"
        }}
        """

        response = self.openai.chat_completion(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You generate Shopify HTML product descriptions with clean formatting."},
                {"role": "user", "content": prompt}
            ]
        )
  
        raw = response.choices[0].message.content
        description = self.extract_json(raw)
        return description, static

    def generate_meta_description(self):
        prompt = f"""
        Generate a product description following these rules:

        - SEO best practices
        - Length up to 160 characters no more!
        - Use keywords: {self.rules.keywords or "None"}
        - The product title is: "{self.title}"

        Return a JSON object where description is:
        {{
        "product_id": "{self.product_id}",
        "description": "<generated/modified meta description>"
        }}
        """

        response = self.openai.chat_completion(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You generate Shopify HTML product meta descriptions with clean formatting."},
                {"role": "user", "content": prompt}
            ]
        )
  
        raw = response.choices[0].message.content
        print("RAW MEETA DESC OUTPUT:", raw)
        description = self.extract_json(raw)
        return description

    def classify_images(self, images: list):
        """
        Accepts a list of image dicts:
        [
            { "id": "gid/.../123", "src": "...", "altText": "" },
            ...
        ]

        Returns list of classification JSONs for each image.
        """
        images = self.normalize_images(images)
        # Build message content for ALL images at once
        content_blocks = [
            {
                "type": "text",
                "text": (
                    "Analyze each product image and return a JSON array. "
                    "For every image include: id, description, objects, colors, "
                    "material, background, detected_features."
                ),
            }
        ]
        print('IMAGESSSSSSS',images)
        # Attach every image
        for img in images:
            content_blocks.append({
                "type": "text",
                "text": f"Image ID: {img['id']}"
            })
            content_blocks.append({
                "type": "image_url",
                "image_url": {"url": img["src"]}
            })

        # Make a single GPT request
        response = self.openai.chat_completion(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert product image classifier."},
                {"role": "user", "content": content_blocks}
            ]
        )

        raw = response.choices[0].message.content
        
        # Expect a JSON array
        try:
            return self.extract_json(raw)
        except:
            print("FAILED TO PARSE JSON:", raw)
            raise

    def normalize_images(self, images):
            """
            Accepts ProductMedia queryset OR list of dicts.
            Returns normalized list of dicts:
            [
                {"id": "...", "src": "...", "altText": "..."}
            ]
            """
            normalized = []

            for img in images:
                # Django model
                if hasattr(img, "shopify_media_id"):
                    normalized.append({
                        "id": img.shopify_media_id,
                        "src": img.src,
                        "altText": img.alt_text or "",
                    })
                # Dict (future-proof)
                elif isinstance(img, dict):
                    normalized.append({
                        "id": img.get("id"),
                        "src": img.get("src"),
                        "altText": img.get("altText", ""),
                    })

            return normalized
    
    def extract_json(self, raw):
        """
        Extract clean JSON from GPT output safely.
        Handles:
        - ```json ... ```
        - ``` ... ```
        - Backticks with spaces
        - Extra text before/after JSON
        """

        if not raw:
            raise ValueError("Empty GPT response")

        # 1. Extract JSON between fences if they exist
        fenced = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
        if fenced:
            raw = fenced.group(1).strip()

        # 2. Remove any stray backticks
        raw = raw.replace("```", "").strip()

        # 3. Ensure it's pure JSON (no leading/trailing text)
        raw = raw.strip()

        # 4. Attempt to parse JSON
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            print("---- RAW CLEANED JSON FAILED ----")
            print(raw)
            raise