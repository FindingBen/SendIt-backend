from rest_framework.serializers import ModelSerializer
from django.contrib.auth.models import User
from .models import Message, ContactList, Contact, Element


class ElementSerializer(ModelSerializer):
    class Meta:
        model = Element
        fields = '__all__'


class MessageSerializer(ModelSerializer):
    element_list = ElementSerializer(many=True)

    class Meta:
        model = Message
        fields = ['id', 'users', 'element_list']

    def create(self, validated_data):

        element_list = validated_data.pop('element_list')
        message = Message.objects.create(**validated_data)

        # for element_data in element_list:
        #     Element.objects.create(**element_data)
        return message

    def update(self, instance, validated_data):

        instance.element_list = validated_data.get(
            'element_list', instance.element_list)
        instance.save()
        return instance

    def get_elements(self, obj):
        elements = obj.element_list.all()
        return ElementSerializer(elements, many=True).data


class UserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']


class RegisterSerializer(ModelSerializer):

    class Meta:
        model = User
        fields = ['username', 'email', 'password']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(
            validated_data['username'], validated_data['email'], validated_data['password'])

        return user


class ContactListSerializer(ModelSerializer):
    class Meta:
        model = ContactList
        fields = ['id', 'list_name']


class ContactSerializer(ModelSerializer):
    class Meta:
        model = Contact
        fields = ['first_name', 'last_name', 'email', 'phone_number']
