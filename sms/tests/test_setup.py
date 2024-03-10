from rest_framework.test import APITestCase
from django.urls import reverse
from django.test import TestCase
import json
import os
from base.tests.helper import RegisterLoginUser
from base.models import CustomUser, PackagePlan, Message, ContactList


class TestSmsSetup(APITestCase):
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
        user.sms_count = 5
        user.package_plan = package_plan
        user.save()
        # Login and get the token
        res = self.client.post(
            helper.login_url, helper.login_data, format='json')
        token = res.data.get('access')

        # Use the token for authentication in subsequent requests
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        return user

    def setUp(self):
        user = self._register_login_user()
        self.create_sms = reverse('sms-send')
        self.create_msg = reverse('create_message')
        self.create_list = reverse('create_list', kwargs={
                                   'id': user.id})
        self.recipients_data = None
        list_data = {
            'list_name': "test_list",
            "users": user,
            "contact_lenght": 3
        }

        message_data = {
            "users": user,
            "message_name": "Test"
        }
        msg = Message.objects.create(**message_data)
        contact_list = ContactList.objects.create(**list_data)

        self.sms_data = {
            "user": user.id,
            "message": msg.id,
            "sender": "test",
            "sms_text": "test",
            "contact_list": contact_list.id,
        }
        current_directory = os.path.dirname(__file__)
        file_path = os.path.join(current_directory, 'recipients.json')
        with open(file_path, 'r') as json_file:
            recipients_data = json.load(json_file)

            self.recipients_data = recipients_data
        return super().setUp()

    def tearDown(self) -> None:
        return super().tearDown()
