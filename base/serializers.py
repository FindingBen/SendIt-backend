from rest_framework.serializers import ModelSerializer
from django.contrib.auth.models import User
from .models import Note, ContactList, Contact


class NoteSerializer(ModelSerializer):
    class Meta:
        model = Note
        fields = '__all__'


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
        fields = ['list_name']


class ContactSerializer(ModelSerializer):
    class Meta:
        model=Contact
        fields = ['first_name','last_name','email','phone_number']