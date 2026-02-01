from django.urls import path
from .views import StripeCheckoutSubscriptionView, StripeCheckoutPurchaseView
from . import views

urlpatterns = [
    path('stripe_checkout_session',
         StripeCheckoutSubscriptionView.as_view(), name='stripe-checkout'),
         path('stripe_checkout_purchase/',
         StripeCheckoutPurchaseView.as_view(), name='stripe-purchase'),
    path('payment_successfull',
         views.payment_successful, name='payment_successful'),
     path('shopify_one_time_charge/',
         views.create_one_time_purchase_charge),
    path('handle_subscription/',
         views.handle_stripe_subscription),
    path('cancel_subscription/',
         views.cancel_stripe_subscription),
    path('payment_cancelled', views.payment_cancelled),
    path('get_charge/',views.check_one_time_charge),
    path('purchases/<str:id>', views.get_purchases),
    path('calculate_plan/', views.calculate_plan_usage,
         name='calculate_package'),
    path('stripe_webhook', views.stripe_webhook, name='stripe_webhook'),
    path('one_time_charge_webhook/',views.stripe_one_time_purchase_webhook),
    path('shopify_status/', views.get_shopify),
    path('shopify_charge/', views.create_shopify_charge),
    path('users_charge/', views.check_users_charge),
    path('user_billings/', views.get_billings),
    path('cancel_shopify_subscription/', views.cancel_shopify_subscription)
]
