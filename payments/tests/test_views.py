from base.tests.helper import RegisterLoginUser
from .test_setup import TestUserPayment, TestUserReciptSetUp
from base.models import CustomUser, PackagePlan
from unittest.mock import patch
from payments.models import UserPayment


class TestStripeAPI(TestUserPayment):

    @patch('payments.views.stripe.checkout.Session.create')
    def test_successful_checkout(self, mock_checkout_session_create):
        mock_checkout_session_create.return_value.id = self.stripe_session_id
        mock_checkout_session_create.return_value.url = 'https://fake-checkout-url.com'

        data = {
            'name_product': self.valid_package_name,
        }

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['url'], 'https://fake-checkout-url.com')
        mock_checkout_session_create.assert_called_once()

    @patch('payments.views.stripe.checkout.Session.create')
    def test_unsuccessful_checkout(self, mock_checkout_session_create):
        mock_checkout_session_create.return_value.id = self.stripe_session_id
        mock_checkout_session_create.return_value.url = 'https://fake-checkout-url.com'

        data = {
            'name_product': "",
        }

        response = self.client.post(self.url, data, format='json')
        print(response.data)
        self.assertEqual(response.status_code, 400)


class TestReciptCreation(TestUserReciptSetUp):

    def _register_login_user(self):
        helper = RegisterLoginUser()
        package_plan = PackagePlan.objects.create(id=1,
                                                  plan_type='Trial', price=0, sms_count_pack=2)
        # Register user
        reg = self.client.post(
            helper.register_url, helper.user_data, format="json")
        email = reg.data['user']['custom_email']
        user = CustomUser.objects.get(custom_email=email)
        user.is_active = True
        user.package_plan = package_plan
        user.save()
        # Login and get the token
        res = self.client.post(
            helper.login_url, helper.login_data, format='json')
        token = res.data.get('access')

        # Use the token for authentication in subsequent requests
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        return user

    def test_successfull_purchase(self):
        user = self._register_login_user()
        user_obj = CustomUser.objects.get(id=user.id)
        user_payment = UserPayment.objects.get(user=user_obj.id)

        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
