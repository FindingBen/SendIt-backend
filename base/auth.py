from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import CustomUser, ShopifyStore
import os
from backend import settings
from openai import OpenAI
import requests
from .queries import GET_SHOPIFY_DATA, GET_SHOP_INFO_2


class OpenAiAuthInit:
    def clientAuth(self):
        client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
        )
        return client
        

class ShopifyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        # Get the Authorization header
        authorization_header = request.headers.get('Authorization')
        if not authorization_header or not authorization_header.startswith('Shopify '):
            print('****SKIPPING SHOPIFY AUTH*****')
            return None  # No Shopify token, skip this authentication class

        # Extract the Shopify token
        shopify_token = authorization_header.split(' ')[1]
        # Validate the Shopify token (optional: verify with Shopify's API)
        if not shopify_token:
            raise AuthenticationFailed('Invalid Shopify token')

        # Retrieve the user associated with the Shopify token
        try:
            shopify = ShopifyStore.objects.get(access_token=shopify_token)

            user = CustomUser.objects.get(
                custom_email=shopify.email)  # Replace with your logic
            return (user, shopify_token)
        except ShopifyStore.DoesNotExist:
            print(
                'No Shopify store associated with this token. Skipping Shopify authentication.')
            return None  # Skip Shopify authentication for non-Shopify users
        except CustomUser.DoesNotExist:
            raise AuthenticationFailed(
                'No user associated with this Shopify token')


def get_shop_info(shop, access_token):

    url = f"https://{shop}/admin/api/2025-01/graphql.json"
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json",
    }

    response = requests.post(url, headers=headers, json={
                             "query": GET_SHOPIFY_DATA})
    data = response.json()

    return data.get('data').get('shop')

def get_business_info(shop, access_token):
    url = f"https://{shop.shop_domain}/admin/api/{settings.SHOPIFY_API_VERSION}/graphql.json"
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json",
    }
    response = requests.post(url, headers=headers, json={
                             "query": GET_SHOP_INFO_2})
    data = response.json()


    return data.get('data').get('shop')
