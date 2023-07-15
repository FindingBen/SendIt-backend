from django.urls import path
from .views import StripeCheckoutVIew
from . import views

urlpatterns = [
    path('stripe_checkout_session', StripeCheckoutVIew.as_view()),
    path('payment_successfull/<str:id>', views.payment_successful),
    path('stripe_webhook', views.stripe_webhook, name='stripe_webhook'),
]
