from django.urls import path
from . import views
from rest_framework_simplejwt.views import (

    TokenRefreshView,
)
from .views import MyTokenObtainPairView
from .views import RegisterAPI, CreateNote

urlpatterns = [
    path('', views.getRoutes),
    path('notes/', views.get_notes),
    path('register/', RegisterAPI.as_view(), name='register'),
    path('create_notes/', CreateNote.as_view()),
    path('create_contact/<str:id>/', views.create_contact),
    path('contact_lists/', views.get_contact_lists),
    path('contact_list/<str:pk>/', views.get_contact_list),
    path('token/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
