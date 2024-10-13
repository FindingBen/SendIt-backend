from rest_framework.serializers import ModelSerializer
from .models import Sms, CampaignStats


class SmsSerializer(ModelSerializer):

    class Meta:
        model = Sms
        fields = '__all__'


class CampaignStatsSerializer(ModelSerializer):

    class Meta:
        model = CampaignStats
        fields = '__all__'
