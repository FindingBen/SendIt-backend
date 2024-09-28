from django.urls import path
from . import views
from .views import createSms


urlpatterns = [
    path('sms-editor/<str:id>', views.get_message),
    path('sms/<str:id>', views.get_sms),
    path('sms-send/', createSms.as_view(), name='sms-send'),
    path('sms-send-schedule/', views.schedule_sms, name='sms-schedule'),
    path('sms/newsletter/<str:id>', views.track_link_click),
    path('sms/button/<str:id>/<str:msgId>', views.track_button_click),
    path('webhooks_delivery', views.vonage_webhook)

]
