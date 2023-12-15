from rest_framework.serializers import ModelSerializer
from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Message, ContactList, Contact, Element, PackagePlan, CustomUser, SurveyResponse


class ElementSerializer(ModelSerializer):
    class Meta:
        model = Element
        fields = '__all__'


class PackageSerializer(ModelSerializer):
    class Meta:
        model = PackagePlan
        fields = '__all__'


class MessageSerializer(ModelSerializer):

    class Meta:
        model = Message
        fields = ['id', 'users', 'created_at', 'status', 'message_name']

    def create(self, validated_data):

        message = Message.objects.create(**validated_data)
        return message

    def update(self, instance, validated_data):
        instance.save()
        return instance


class UserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']


class CustomUserSerializer(ModelSerializer):
    package_plan = PackageSerializer()

    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email',
                  'first_name', 'last_name', 'package_plan', 'sms_count', 'is_active']

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class RegisterSerializer(ModelSerializer):

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password',
                  'first_name', 'last_name', 'package_plan', 'is_active']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        validated_data['is_active'] = False
        user = CustomUser.objects.create_user(
            **validated_data)

        return user


class ContactListSerializer(ModelSerializer):
    class Meta:
        model = ContactList
        fields = ['id', 'list_name', 'contact_lenght']


class ContactSerializer(ModelSerializer):
    class Meta:
        model = Contact
        fields = ['id', 'first_name', 'last_name', 'email', 'phone_number']


class SurveySerializer(ModelSerializer):
    class Meta:
        model = SurveyResponse
        fields = '__all__'


class ChangePasswordSerializer(serializers.Serializer):
    model = User

    """
    Serializer for password change endpoint.
    """
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
