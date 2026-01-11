from django.urls import path
from .views import NotificationView, OptimizationJobView
from . import views

urlpatterns = [
    path('get_notifications', NotificationView.as_view()),
    path("get_notifications/<int:notification_id>/", NotificationView.as_view(), name="notifications-detail"),
    path('optimize_job', OptimizationJobView.as_view()),
    path('optimization_numbers/',views.optimization_quota)


]
