from rest_framework.serializers import ModelSerializer
from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Message, ContactList, Contact, Element, PackagePlan, CustomUser


class ElementSerializer(ModelSerializer):
    class Meta:
        model = Element
        fields = '__all__'


class PackageSerializer(ModelSerializer):
    class Meta:
        model = PackagePlan
        fields = '__all__'


class MessageSerializer(ModelSerializer):
    element_list = ElementSerializer(many=True)

    class Meta:
        model = Message
        fields = ['id', 'users', 'element_list']

    def create(self, validated_data):

        element_list = validated_data.pop('element_list')
        message = Message.objects.create(**validated_data)
        return message

    def update(self, instance, validated_data):
        instance.save()
        return instance

    def get_elements(self, obj):
        elements = obj.element_list.all()
        return ElementSerializer(elements, many=True).data


class UserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']


class CustomUserSerializer(ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email',
                  'first_name', 'last_name', 'package_plan', 'sms_count']

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class RegisterSerializer(ModelSerializer):

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password',
                  'first_name', 'last_name', 'package_plan']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = CustomUser.objects.create_user(
            **validated_data)

        return user


class ContactListSerializer(ModelSerializer):
    class Meta:
        model = ContactList
        fields = ['id', 'list_name']


class ContactSerializer(ModelSerializer):
    class Meta:
        model = Contact
        fields = ['id', 'first_name', 'last_name', 'email', 'phone_number']


class ChangePasswordSerializer(serializers.Serializer):
    model = User

    """
    Serializer for password change endpoint.
    """
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
