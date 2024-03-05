from django.urls import path, include
from . import views
from rest_framework_simplejwt.views import (
    TokenRefreshView,
)
from .views import MyTokenObtainPairView
from .views import RegisterAPI, CreateNote, CreateElement, SendEmailConfirmationTokenAPIView


urlpatterns = [
    path('notes/', views.get_notes),
    path('register/', RegisterAPI.as_view(), name='register'),
    path('create_notes/', CreateNote.as_view()),
    path('create_element/', CreateElement.as_view()),
    path('update_element/<str:id>/', views.update_element),
    # Message
    path('view/<str:id>/', views.note_view),
    path('message_view_edit/<str:id>/', views.update_message),
    path('delete_message/<str:id>', views.delete_message),
    path('delete_element/<str:id>/', views.delete_element),
    # Contact list and contacts
    path('create_contact/<str:id>/', views.create_contact),
    path('contact_lists/', views.get_contact_lists),
    path('contact_list/<str:id>/', views.get_contacts),
    path('contact_detail/<str:id>', views.contact_detail),
    path('delete_recipient/<str:id>/', views.delete_contact_recipient),
    path('delete_list/<str:id>', views.delete_contact_list),
    # Package plan
    path('package_plan/', views.get_packages),
    path('package_purchase/<str:id>/', views.purchase_package),
    # User account
    path('user_account/<str:id>/', views.get_user),
    path('update_user/<str:id>/', views.update_user),
    path('create_list/<str:id>', views.create_list),
    # Opt out
    path('optout/<str:id>', views.handle_unsubscribe),
    #Analytics
    path('get_analytcs/<int:record_id>/', views.get_analytics_data),
    path('get_survey_results/<str:id>', views.get_results),
    path('get_total_analytic_values/<str:id>', views.get_total_analytic_values),
    path('handle_survey/<str:id>', views.handle_survey_response),
    # Toekn
    path('token/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # Password
    path('set_password/',
         include('django_rest_passwordreset.urls', namespace='set_password')),
    # Email confirmation
    path('confirm_email_verification/',
         SendEmailConfirmationTokenAPIView.as_view()),
    path('confirmation_token/<str:token_id>/<str:user_id>/',
         views.confirmation_token_view)
]
