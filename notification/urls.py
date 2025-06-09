from django.urls import path
from .views import NotificationView

urlpatterns = [
    path('get_notifications', NotificationView.as_view()),

]
