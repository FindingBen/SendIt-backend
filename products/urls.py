from django.urls import path
from .views import ProductView, PromptAnalysis, ProductOptimizeView, MerchantApprovalProductOptimization
from . import views
from . import webhooks

urlpatterns = [
    path('shopify_products/', ProductView.as_view()),
    path('shopify_products/<str:id>/', ProductView.as_view()), 
    path('import_bulk_products/', views.import_bulk_products),
    path('optimize_shopify_product/',MerchantApprovalProductOptimization.as_view()),
    # product webhooks
    path('product_webhook', webhooks.create_product_webhook),
    path('delete_product_webhook', webhooks.delete_product_webhook),
    path('update_product_webhook', webhooks.update_product_webhook),
    path('shopify_webhooks/', views.register_webhooks),
    path('product_optimize/', ProductOptimizeView.as_view()),
    path('business_analysis/', PromptAnalysis.as_view()),
]
