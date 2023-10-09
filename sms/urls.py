from django.urls import path
from . import views
from .views import createSms, ScheduleSms


urlpatterns = [
    path('sms-editor/<str:id>', views.get_message),
    path('sms/<str:id>', views.get_sms),
    path('sms-send/', createSms.as_view()),
    path('sms-send-schedule/', ScheduleSms.as_view()),
    path('sms/tracking/<str:uuid>', views.track_link_click),
    path('webhooks_delivery', views.vonage_webhook)

]
