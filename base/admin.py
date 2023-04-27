from django.contrib import admin
from .models import Note, Contact, ContactList

admin.site.register(Note)
admin.site.register(Contact)
admin.site.register(ContactList)
