from django.contrib import admin
from .models import Message, Contact, ContactList, ShopifyStore, Element, PackagePlan, CustomUser, CarouselImage, EmailConfirmationToken, SurveyResponse, AnalyticsData, QRCode

admin.site.register(Message)
admin.site.register(Contact)
admin.site.register(ContactList)
admin.site.register(Element)
admin.site.register(PackagePlan)
admin.site.register(CustomUser)
admin.site.register(SurveyResponse)
admin.site.register(EmailConfirmationToken)
admin.site.register(AnalyticsData)
admin.site.register(QRCode)
admin.site.register(ShopifyStore)
admin.site.register(CarouselImage)
