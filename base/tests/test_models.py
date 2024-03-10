from django.test import TestCase
from base.models import CustomUser, PackagePlan


class TestUserModel:
    def setUp(self):
        # Create a sample PackagePlan instance for testing
        package_plan = PackagePlan.objects.create(
            plan_type='Basic', sms_count_pack=100)

        # Create a sample CustomUser instance for testing
        self.user = CustomUser.objects.create(
            username='test_user',
            email='test@example.com',
            sms_count=50,
            user_type='Independent',
            custom_email='test@example.com',
            package_plan=package_plan
        )

    def test_save_method_new_instance(self):
        # Test the save method for a new instance of CustomUser
        new_user = CustomUser(
            username='new_user',
            email='new_user@example.com',
            sms_count=10,
            user_type='Business',
            custom_email='new_user@example.com'
        )
        new_user.save()

        # Retrieve the saved instance from the database
        saved_user = CustomUser.objects.get(username='new_user')

        # Perform assertions to check if the save method behaves as expected
        self.assertEqual(saved_user.package_plan.plan_type, 'Basic')
        # Check if sms_count is updated based on package_plan
        self.assertEqual(saved_user.sms_count, 12)

    def test_save_method_existing_instance(self):
        # Test the save method for an existing instance of CustomUser
        self.user.package_plan.sms_count_pack = 200
        self.user.package_plan.save()  # Update the sms_count_pack value

        # Save the existing user instance
        self.user.save()

        # Retrieve the updated instance from the database
        updated_user = CustomUser.objects.get(username='test_user')

        # Perform assertions to check if the save method behaves as expected for an existing instance
        self.assertEqual(updated_user.package_plan.plan_type, 'Basic')
        # Check if sms_count is updated based on the updated package_plan
        self.assertEqual(updated_user.sms_count, 250)

    def test_serialize_package_plan(self):
        # Test the serialize_package_plan method
        serialized_data = self.user.serialize_package_plan()

        # Perform assertions to check if the serialization method behaves as expected
        self.assertEqual(serialized_data['package_plan'], 'Basic')
        # Check if sms_count is correctly included in the serialization
        self.assertEqual(serialized_data['sms_count'], 50)
