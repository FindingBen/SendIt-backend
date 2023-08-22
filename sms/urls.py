from django.urls import path
from . import views
from .views import createSms


urlpatterns = [
    path('sms-editor/<str:id>', views.get_message),
    path('sms-send/', createSms.as_view()),

]
