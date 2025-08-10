from django.contrib import admin
from .models import UserPayment, Purchase, StripeEvent

admin.site.register(UserPayment)
admin.site.register(Purchase)
admin.site.register(StripeEvent)
