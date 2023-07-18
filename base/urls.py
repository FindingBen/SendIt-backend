from django.urls import path, include
from . import views
from rest_framework_simplejwt.views import (

    TokenRefreshView,
)
from .views import MyTokenObtainPairView
from .views import RegisterAPI, CreateNote, CreateElement

urlpatterns = [
    path('notes/', views.get_notes),
    path('register/', RegisterAPI.as_view(), name='register'),
    path('create_notes/', CreateNote.as_view()),
    path('create_element/', CreateElement.as_view()),
    path('message_view/<str:id>/', views.note_view),
    path('message_view_edit/<str:id>/', views.update_message),
    path('delete_message/<str:id>', views.delete_message),
    path('delete_element/<str:id>/', views.delete_element),
    path('create_contact/<str:id>/', views.create_contact),
    path('contact_lists/', views.get_contact_lists),
    path('contact_list/<str:id>/', views.get_contacts),
    path('package_plan/', views.get_packages),
    path('user_account/<str:id>/', views.get_user),
    path('update_user/<str:id>/', views.update_user),
    path('create_list/<str:id>', views.create_list),
    path('delete_recipient/<str:id>/', views.delete_contact_recipient),
    path('package_purchase/<str:id>/', views.purchase_package),
    path('token/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('password_reset/',
         include('django_rest_passwordreset.urls', namespace='password_reset')),
    path('set_password/',
         include('django_rest_passwordreset.urls', namespace='set_password')),

]
