from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import CustomUser, ShopifyStore


class ShopifyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        # Get the Authorization header
        authorization_header = request.headers.get('Authorization')
        if not authorization_header or not authorization_header.startswith('Shopify '):
            return None  # No Shopify token, skip this authentication class

        # Extract the Shopify token
        shopify_token = authorization_header.split(' ')[1]

        # Validate the Shopify token (optional: verify with Shopify's API)
        if not shopify_token:
            raise AuthenticationFailed('Invalid Shopify token')

        # Retrieve the user associated with the Shopify token
        try:
            shopify = ShopifyStore.objects.get(access_token=shopify_token)
            user_object = shopify.user
            user = CustomUser.objects.get(
                id=user_object.id)  # Replace with your logic
        except CustomUser.DoesNotExist:
            raise AuthenticationFailed(
                'No user associated with this Shopify token')

        return (user, shopify_token)
