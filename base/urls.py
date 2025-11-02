from django.urls import path, include
from . import views
from rest_framework_simplejwt.views import (
    TokenRefreshView,
)
from .views import MyTokenObtainPairView, OAuthAuthorization, CallbackAuthView
from .views import RegisterAPI, CreateNote, CreateElement, CustomUserViewSet, SendEmailConfirmationTokenAPIView, ShopifyAuth, ContactListsView
from django.http import JsonResponse


urlpatterns = [
    path('notes/', views.get_notes),
    path('active_campaigns/', views.get_active_campaigns),
    path('get_user/', views.get_user),
    path('scheduled_campaigns/', views.get_scheduled_campaigns),
    path('register/', RegisterAPI.as_view(), name='register'),
    path('create_notes/', CreateNote.as_view(), name='create_message'),
    path('create_element/', CreateElement.as_view(), name='create_element'),
    path('update_element/<str:id>/', views.update_element),
    # Message
    path('view/<str:id>/', views.note_view),
    path('view_archives/', views.get_arvhived),
    path('message_view_edit/<str:id>/', views.update_message),
    path('delete_message/<str:id>', views.delete_message),
    path('delete_element/<str:id>/', views.delete_element),
    # Contact list and contacts
    path('create_contact/<str:id>/', views.create_contact, name='create_contact'),
    path('create_contact_qr/<str:id>', views.create_contact_via_qr),
    path('contact_lists/', ContactListsView.as_view()),
    path('contact_list/<str:id>/', views.get_contacts),
    path('contact_detail/<str:id>', views.contact_detail),
    #     path('contact_detail/', views.contact_detail),
    path('upload_bulk_contacts/', views.upload_bulk_contacts),
    path('create_bulk_contacts/', views.bulk_create_contacts),
    path('delete_recipient/<int:id>', views.delete_contact_recipient),
    # Package plan
    path('package_plan/', views.get_packages),
    path('package_purchase/<str:id>/', views.purchase_package),
    # User account
    path('user_account/<str:id>/', views.get_user),
    path('update_user/<str:id>/', views.update_user),
    # Opt out
    path('optout/<str:id>', views.handle_unsubscribe),
    # QR
    path('qr_code/<str:id>', views.get_qr_code),
    path('qr_check_sign/<str:id>', views.check_limit),
    # Analytics
    path('get_analytcs/<int:record_id>/', views.get_analytics_data),
    path('get_survey_results/<str:id>', views.get_results),
    path('get_total_analytic_values/<str:id>', views.get_total_analytic_values),
    path('handle_survey/<str:id>', views.handle_survey_response),
    path('export_analytics/<str:id>', views.export_analytics),
    # Toekn
    path('token/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('oAuth-login', OAuthAuthorization.as_view()),
    path('callback', CallbackAuthView.as_view()),
    path('shopify-auth/',
         ShopifyAuth.as_view(), name='token_obtain_pair'),
    # Password
    path('users/set_password/',
         CustomUserViewSet.as_view({'post': 'set_password'}), name='set_password'),
    # Email confirmation
    path('confirm_email_verification/',
         SendEmailConfirmationTokenAPIView.as_view()),
    path('confirmation_token/<str:token_id>/<str:user_id>/',
         views.confirmation_token_view),
    # Shopify products
    path('shopify_products/', views.get_shopify_products_orders),
    path('shopify_product/', views.get_product),
    path('shopify_product_insights/', views.get_insights),
    path('shop_info/', views.get_shop_shopify),
    # Shopify orders
    path('shopify_orders/', views.get_shop_orders),
    # Webhooks
    path('customer_data_webhook', views.customer_data_request_webhook),
    path('customer_redact_data_webhook', views.customer_redact_request_webhook),
    path('customer_shop_redact_webhook',
         views.customer_shop_redact_request_webhook),

]
