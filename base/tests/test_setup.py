from rest_framework.test import APITestCase, APIClient
from django.urls import reverse
from base.models import PackagePlan, CustomUser, ContactList


class TestAuthSetUp(APITestCase):

    def setUp(self):
        self.register_url = reverse('register')
        self.login_url = reverse('token_obtain_pair')

        self.user_data = {
            "custom_email": "test@gmail.com",
            "username": "test",
            "password": "Dusica123!",
            "re_password": "Dusica123!",
            "user_type": "Independent",
            "is_active": "false",
            "sms_count": 0
        }

        self.login_data = {
            "username": "test",
            "password": "Dusica123!"
        }

        self.package = PackagePlan.objects.create(id=1,
                                                  plan_type='Trial', price=0, sms_count_pack=2)

        return super().setUp()

    def tearDown(self) -> None:
        return super().tearDown()


class TestContactListSetUp(APITestCase):

    def setUp(self):
        self.package = PackagePlan.objects.create(id=1,
                                                  plan_type='Trial', price=0, sms_count_pack=2)
        self.register_url = reverse('register')
        self.login_url = reverse('token_obtain_pair')
        self.create_list = reverse('create_list', kwargs={
                                   'id': 4})

        self.user_data_reg = {
            "custom_email": "test@gmail.com",
            "username": "test",
            "password": "Dusica123!",
            "re_password": "Dusica123!",
            "user_type": "Independent",
            "is_active": True,
            "sms_count": 0
        }

        self.login_data = {
            "username": "test",
            "password": "Dusica123!"
        }

        self.list_data = {
            'list_name': "test_list"
        }

        self.empty_data = {
            "list_name": ""
        }

        return super().setUp()

    def tearDown(self) -> None:
        return super().tearDown()


class TestRecipientSetUp(APITestCase):

    def setUp(self):

        self.contact_data = {
            "first_name": "John",
            "last_name": "Smith",
            "phone_number": "555333",
            "email": "john@gmail.com",
        },

        return super().setUp()

    def tearDown(self) -> None:
        return super().tearDown()


class TestMessageSetUp(APITestCase):

    def setUp(self):

        self.create_message = reverse('create_message')

        return super().setUp()

    def tearDown(self) -> None:
        return super().tearDown()


class TestElementsSetUp(APITestCase):

    def setUp(self):
        self.create_element = reverse('create_element')

        return super().setUp()

    def tearDown(self) -> None:
        return super().tearDown()


