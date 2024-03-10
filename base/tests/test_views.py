from .test_setup import TestAuthSetUp, TestContactListSetUp, TestRecipientSetUp, TestMessageSetUp, TestElementsSetUp
from base.models import CustomUser, PackagePlan, ContactList, Message
from django.contrib.auth import get_user_model
from .helper import RegisterLoginUser
import pdb
from django.urls import reverse

"""Tests for Custom user authentication and registration"""


class TestAuthViews(TestAuthSetUp):

    def test_user_auth_without_verification(self):
        self.client.post(
            self.register_url, self.user_data, format="json")
        response = self.client.post(
            self.login_url, self.login_data, format='json')
        self.assertEqual(response.status_code, 401)

    def test_user_auth_with_verification(self):
        response = self.client.post(
            self.register_url, self.user_data, format='json')

        # pdb.set_trace()
        email = response.data['user']['custom_email']

        user = CustomUser.objects.get(custom_email=email)
        user.is_active = True
        package_obje = self.package
        user.package_plan = package_obje
        user.save()
        res = self.client.post(self.login_url, self.login_data, format='json')
        self.assertEqual(res.status_code, 200)

    def test_empty_register_request(self):
        response = self.client.post(self.register_url)
        self.assertEqual(response.status_code, 400)

    def test_user_register(self):

        response = self.client.post(
            self.register_url, self.user_data, format="json")
        package_obje = self.package
        user = CustomUser.objects.get(
            custom_email=response.data['user']['custom_email'])
        user.package_plan = package_obje
        user.save()
        self.assertEqual(response.status_code, 201)


"""Tests for Contact List"""


class TestContactListViews(TestContactListSetUp):

    def _register_login_user(self):
        # Register user
        reg = self.client.post(
            self.register_url, self.user_data_reg, format="json")
        email = reg.data['user']['custom_email']
        user = get_user_model().objects.get(email=email)
        user.is_active = True
        user.save()

        # Login and get the token
        res = self.client.post(self.login_url, self.login_data, format='json')
        token = res.data.get('access')

        # Use the token for authentication in subsequent requests
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_create_contact_list(self):
        self._register_login_user()
        response = self.client.post(
            self.create_list, self.list_data, format='json')

        self.assertEqual(response.status_code, 201)

    def test_empty_data_submit(self):
        self._register_login_user()
        response = self.client.post(
            self.create_list, self.empty_data, format='json')

        self.assertEqual(response.status_code, 400)


"""Tests for Contact recipients"""


class TestRecipientsViews(TestRecipientSetUp):

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
        # Contact list
        contact_list = ContactList.objects.create(
            list_name='Test', users=user)
        # Login and get the token
        res = self.client.post(
            helper.login_url, helper.login_data, format='json')
        token = res.data.get('access')

        # Use the token for authentication in subsequent requests
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        return contact_list

    def test_add_recipient(self):

        contact_list = self._register_login_user()
        contact_data = {
            "first_name": "John",
            "last_name": "Smith",
            "phone_number": "555333",
            "email": "john@gmail.com",
            'contact_list': contact_list.id
        }
        url = reverse('create_contact', kwargs={'id': contact_list.id})
        res = self.client.post(url,
                               contact_data, format='json')
        self.assertEqual(res.status_code, 201)

    def test_add_empty_recipient(self):
        contact_list = self._register_login_user()
        url = reverse('create_contact', kwargs={'id': contact_list.id})
        contact_data = {}
        res = self.client.post(url,
                               contact_data, format='json')
        self.assertEqual(res.status_code, 400)


"""Tests for Message"""


class TestMessageViews(TestMessageSetUp):

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

    def test_empty_message_create(self):
        user = self._register_login_user()
        message_data = {
            "users": user.id,
            "message_name": ""
        }
        res = self.client.post(self.create_message,
                               message_data, format='json')
        self.assertEqual(res.status_code, 400)

    def test_message_create(self):
        user = self._register_login_user()
        message_data = {
            "users": user.id,
            "message_name": "Test"
        }
        res = self.client.post(self.create_message,
                               message_data, format='json')
        self.assertEqual(res.status_code, 200)


"""Tests for Elements of message"""


class TestElementsViews(TestElementsSetUp):
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

    def test_create_empty_text_element(self):

        user = self._register_login_user()

        message = Message.objects.create(message_name='Test', users=user)

        element_data = {
            "message": message.id,
            "text": "",
            "element_type": "Text",
            "order": 1
        }
        res = self.client.post(self.create_element,
                               element_data, format='json')

        self.assertEqual(res.status_code, 400)

    def test_create_text_element(self):
        user = self._register_login_user()

        message = Message.objects.create(message_name='Test', users=user)

        element_data = {
            "message": message.id,
            "text": "test",
            "element_type": "Text",
            "order": 1
        }
        res = self.client.post(self.create_element,
                               element_data, format='json')
        self.assertEqual(res.status_code, 200)

    def test_create_empty_button_element(self):
        user = self._register_login_user()

        message = Message.objects.create(message_name='Test', users=user)

        element_data = {
            "message": message.id,
            "button_title": "",
            "element_type": "Button",
            "order": 2
        }
        res = self.client.post(self.create_element,
                               element_data, format='json')
        self.assertEqual(res.status_code, 400)

    def test_create_button_element(self):
        user = self._register_login_user()

        message = Message.objects.create(message_name='Test', users=user)

        element_data = {
            "message": message.id,
            "button_title": "test",
            "element_type": "Button",
            "order": 2
        }
        res = self.client.post(self.create_element,
                               element_data, format='json')
        self.assertEqual(res.status_code, 200)

    def test_create_empty_survey(self):
        user = self._register_login_user()

        message = Message.objects.create(message_name='Test', users=user)

        element_data = {
            "message": message.id,
            "survey": "",
            "element_type": "Survey",
            "order": 3
        }
        res = self.client.post(self.create_element,
                               element_data, format='json')
        self.assertEqual(res.status_code, 400)

    def test_create_survey(self):
        user = self._register_login_user()

        message = Message.objects.create(message_name='Test', users=user)

        element_data = {
            "message": message.id,
            "survey": "Test",
            "element_type": "Survey",
            "order": 3
        }
        res = self.client.post(self.create_element,
                               element_data, format='json')
        self.assertEqual(res.status_code, 200)
