from django.contrib import admin
from .models import UserPayment, Purchase

admin.site.register(UserPayment)
admin.site.register(Purchase)
