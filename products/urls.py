from django.urls import path
from .views import ProductView
from . import views

urlpatterns = [
    path('shopify_products/', ProductView.as_view()),
    path('import_bulk_products/', views.import_bulk_products)
]
