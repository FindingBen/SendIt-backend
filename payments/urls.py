from django.urls import path
from .views import StripeCheckoutVIew
from . import views

urlpatterns = [
    path('stripe_checkout_session',
         StripeCheckoutVIew.as_view(), name='stripe-checkout'),
    path('payment_successfull/<str:id>',
         views.payment_successful, name='payment_successful'),
    path('payment_cancelled', views.payment_cancelled),
    path('purchases/<str:id>', views.get_purchases),
    path('calculate_plan/', views.calculate_plan_usage,
         name='calculate_package'),
    path('stripe_webhook', views.stripe_webhook, name='stripe_webhook'),
]
