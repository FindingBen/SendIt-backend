from rest_framework.permissions import BasePermission
from .models import Contact, CustomUser


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
        print(custom_user)
        package_plan = custom_user.package_plan

        package_limits = {
            'Trial Plan': 10,
            'Basic package': 1000,
            'Silver package': 3000,
            'Gold package': 8000,
        }

        # Get the limit for the user's package plan
        limit = package_limits.get(package_plan.plan_type, 0)

        # Count the user's current contacts
        current_contacts_count = Contact.objects.filter(
            users=custom_user).count()
        # Check if the user has reached their limit
        if current_contacts_count >= limit:
            return False  # Deny access if the limit is reached

        return True
