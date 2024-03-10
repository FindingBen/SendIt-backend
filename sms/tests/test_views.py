from .test_setup import TestSmsSetup
from base.tests.helper import RegisterLoginUser
from unittest.mock import patch
from base.models import PackagePlan, CustomUser, Message
from django.urls import reverse


class TestSms(TestSmsSetup):


    def test_send_sms(self):
        """Create-Send sms successfully"""
        res = self.client.post(self.create_sms, self.sms_data, format='json')

        print(res.data)
        self.assertEqual(res.status_code, 200)


        """Try to send sms with insifficient sms credit"""
        res = self.client.post(self.create_sms, self.sms_data, format='json')
        self.assertEqual(res.status_code, 405)
