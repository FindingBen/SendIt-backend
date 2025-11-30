from django.urls import path
from .views import ProductView, PromptAnalysis, ProductOptimizeView
from . import views
from . import webhooks

urlpatterns = [
    path('shopify_products/', ProductView.as_view()),
    path('import_bulk_products/', views.import_bulk_products),
    # product webhooks
    path('product_webhook', webhooks.create_product_webhook),
    path('shopify_webhooks/', views.register_webhooks),
    path('product_optimize/', ProductOptimizeView.as_view()),
    path('business_analysis/', PromptAnalysis.as_view()),
]
