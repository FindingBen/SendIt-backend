from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('base.urls')),
    path('sms/', include('sms.urls')),
    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.jwt')),
    path('stripe/', include('payments.urls'))
]


urlpatterns += static(settings.MEDIA_URL,
                      document_root=settings.MEDIA_ROOT)
