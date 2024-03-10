from rest_framework.test import APITestCase, APIClient
from django.urls import reverse
from django.test import TestCase
from unittest.mock import patch
import stripe
from django.conf import settings
from decimal import Decimal
from django.core.cache import cache


class TestUserPayment(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('stripe-checkout')
        # Set up stripe mock
        self.stripe_session_id = 'fff123fff123'
        stripe.checkout.Session.create = self.stripe_session_id
        self.valid_package_name = settings.ACTIVE_PRODUCTS[0][0]

        return super().setUp()

    def tearDown(self) -> None:
        return super().tearDown()


class TestUserReciptSetUp(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.stripe_session_id = 'fff123fff123'
        self.url = reverse('payment_successful', kwargs={
                           'id': self.stripe_session_id})

        return super().setUp()

    def tearDown(self) -> None:
        return super().tearDown()
