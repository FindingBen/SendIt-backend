from django.urls import path
from .views import NotificationView, OptimizationJobView

urlpatterns = [
    path('get_notifications', NotificationView.as_view()),
    path('optimize_job', OptimizationJobView.as_view()),


]
