from django.contrib import admin
from .models import Message, Contact, ContactList, Element, PackagePlan

admin.site.register(Message)
admin.site.register(Contact)
admin.site.register(ContactList)
admin.site.register(Element)
admin.site.register(PackagePlan)
