from django.urls import path
from . import views
from .views import createSms


urlpatterns = [
    path('sms-editor/<str:id>', views.get_message),
    path('sms/<str:id>', views.get_sms),
    path('sms-send/', createSms.as_view(), name='sms-send'),
    path('sms-send-schedule/', views.schedule_sms,name='sms-schedule'),
    path('sms/tracking/<str:uuid>', views.track_link_click),
    path('webhooks_delivery', views.vonage_webhook)

]
