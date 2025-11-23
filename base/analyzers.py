import json


class Prompting:
    @staticmethod
    def init_process(client,business_data):
        
        return Prompting.analyze_business(client,business_data)
    
    @staticmethod
    def analyze_business(client,business_data):
        prompt = f"""
        You are an ecommerce business classifier.
        Based on the following Shopify store data: {business_data}

        Identify:
        - The business niche
        - What products they likely sell
        - Target audience
        - Brand tone/voice
        - Professionalism level (1-10)
        - Recommended SEO ruleset for product info(make sure to keep reccomended_seo_ruleset always the same name as column):
            - product_name_rule
            - product_description_rule
            - product_image_rule
            - product_variant_rule
            - product_tag_rule
            - product_alt_image_rule
        Return a JSON object.
        """

        response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        )
        content = response.choices[0].message.content
        return json.loads(content)
