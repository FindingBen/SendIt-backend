from rest_framework.serializers import ModelSerializer
from django.contrib.auth.models import User
from .models import Sms


class SmsSerializer(ModelSerializer):
    class Meta:
        model = Sms
        fields = '__all__'
