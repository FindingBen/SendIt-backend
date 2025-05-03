from rest_framework.permissions import BasePermission
from .models import Contact, CustomUser
from .queries import GET_TOTAL_CUSTOMERS_NR
from .shopify_functions import ShopifyFactoryFunction


class HasPackageLimit(BasePermission):
    """
    Custom permission to check if the user has reached their package limit.
    """
    message = "You have reached the maximum number of contacts allowed for your package."
    # Define package limits

    def has_permission(self, request, view):
        # Fetch the user's package plan
        user_id = request.user.id
        custom_user = CustomUser.objects.get(user_ptr_id=user_id)
        package_plan = custom_user.package_plan

        package_limits = {
            'Trial Plan': 5,
            'Basic package': 200,
            'Silver package': 1000,
            'Gold package': 5000,
        }

        # Get the limit for the user's package plan
        limit = package_limits.get(package_plan.plan_type, 0)

        shopify_domain = request.headers.get('shopify-domain', None)
        if shopify_domain:

            url = f"https://{shopify_domain}/admin/api/2025-01/graphql.json"
            shopify_token = request.headers['Authorization'].split(' ')[1]
            shopify_factory = ShopifyFactoryFunction(
                GET_TOTAL_CUSTOMERS_NR, shopify_domain, shopify_token, url, request=request)

            current_contacts_count = shopify_factory.get_total_customers()
            if current_contacts_count >= limit:
                return False
        # Count the user's current contacts
        current_contacts_count = Contact.objects.filter(
            users=custom_user).count()
        # Check if the user has reached their limit
        if current_contacts_count >= limit:
            return False  # Deny access if the limit is reached

        return True
