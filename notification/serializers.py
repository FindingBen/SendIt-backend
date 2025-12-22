from rest_framework import serializers
from .models import Notification, OptimizationJob


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'
        read_only_fields = ['user', 'created_at']


class OptimizationJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = OptimizationJob
        fields = '__all__'