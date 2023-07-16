from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import AccessToken
from .serializers import MessageSerializer, RegisterSerializer, UserSerializer, CustomUserSerializer, ContactListSerializer, ContactSerializer, ElementSerializer, PackageSerializer, ChangePasswordSerializer
from .models import Message, ContactList, Contact, Element, PackagePlan, CustomUser
from rest_framework import generics
from django.contrib.auth.models import User
from django.contrib.auth.views import PasswordResetView
from django.contrib.messages.views import SuccessMessageMixin


class ChangePasswordView(generics.UpdateAPIView):
    """
    An endpoint for changing password.
    """
    serializer_class = ChangePasswordSerializer
    model = CustomUser
    permission_classes = (IsAuthenticated,)

    def get_object(self, queryset=None):
        obj = self.request.user
        return obj

    def update(self, request, *args, **kwargs):
        self.object = self.get_object()
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # Check old password
            if not self.object.check_password(serializer.data.get("old_password")):
                return Response({"old_password": ["Wrong password."]}, status=status.HTTP_400_BAD_REQUEST)
            # set_password also hashes the password that the user will get
            self.object.set_password(serializer.data.get("new_password"))
            self.object.save()
            response = {
                'status': 'success',
                'code': status.HTTP_200_OK,
                'message': 'Password updated successfully',
                'data': []
            }

            return Response(response)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims
        token['username'] = user.username
        # token['package_plan'] = user.package_plan
        # ...

        return token


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user(request, id):
    user = CustomUser.objects.get(id=id)
    serializer = CustomUserSerializer(user)

    return Response(serializer.data)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_user(request, id):
    user = CustomUser.objects.get(id=id)
    serializer = CustomUserSerializer(user, data=request.data, partial=True)
    if serializer.is_valid(raise_exception=True):

        serializer.update(user, validated_data=request.data)
        return Response(serializer.data, status=status.HTTP_200_OK)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def note_view(request, id):
    message = Message.objects.get(id=id)

    serializer = MessageSerializer(message)

    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_notes(request):
    user = request.user
    notes = user.message_set.all()
    serializer = MessageSerializer(notes, many=True)

    return Response(serializer.data)

# Contact lists


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_packages(request):
    package = PackagePlan.objects.all()
    serializer = PackageSerializer(package, many=True)

    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_contact_lists(request):
    user = request.user
    contact_list = user.contactlist_set.all()
    serializer = ContactListSerializer(contact_list, many=True)

    return Response(serializer.data)


@api_view(['GET,PUT'])
@permission_classes([IsAuthenticated])
def get_contact_list(request, pk):
    user = request.user
    contact_list = ContactList.objects.get(id=pk)
    serializer = ContactListSerializer(contact_list)

    return Response(serializer.data)

# Contact list


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_contacts(request, id):
    contact_list = ContactList.objects.get(id=id)
    contact = Contact.objects.filter(contact_list=contact_list)
    serializer = ContactSerializer(contact, many=True)

    return Response(serializer.data)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_message(request, id):
    message = Message.objects.get(id=id)
    serializer = MessageSerializer(message, data=request.data)
    if serializer.is_valid(raise_exception=True):

        for element_obj in request.data['element_list']:
            element = Element.objects.get(id=element_obj['element']['id'])
            message.element_list.add(element)

        serializer.update(message, validated_data=request.data['element_list'])
        return Response(serializer.data, status=status.HTTP_200_OK)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_contact(request, id):

    contact_list = ContactList.objects.get(id=id)
    serializer = ContactSerializer(data=request.data)
    # serializer.contact_list = contact_list
    if serializer.is_valid(raise_exception=True):
        serializer.save(contact_list=contact_list)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def purchase_package(request, id):
    user = CustomUser.objects.get(id=id)
    package_plan = PackagePlan.objects.get(id=request.data['package_plan'])

    user.package_plan = package_plan
    user.save()

    serializer = CustomUserSerializer(user)
    return Response(serializer.data, status=status.HTTP_200_OK)


class RegisterAPI(generics.GenericAPIView):
    serializer_class = RegisterSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({
            "user": CustomUserSerializer(user, context=self.get_serializer_context()).data
        })


class CreateNote(generics.GenericAPIView):
    serializer_class = MessageSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = serializer.save()

        for element_obj in request.data['element_list']:

            element = Element.objects.get(id=element_obj['element']['id'])
            message.element_list.add(element)

        return Response({
            "note": MessageSerializer(message, context=self.get_serializer_context()).data
        })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_list(request, id):
    user = CustomUser.objects.get(id=id)
    serializer = ContactListSerializer(data=request.data)
    if serializer.is_valid(raise_exception=True):
        serializer.save(users=user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CreateElement(generics.GenericAPIView):
    serializer_class = ElementSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        element = serializer.save()
        return Response({
            "element": ElementSerializer(element, context=self.get_serializer_context()).data
        })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_message(request, id):

    message = Message.objects.get(id=id)
    message.delete()
    return Response("Message deleted!")


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_element(request, id):

    element = Element.objects.get(id=id)
    element.delete()
    return Response("Message deleted!")


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_contact_recipient(request, id):

    contact = Contact.objects.get(id=id)
    contact.delete()
    return Response("Message deleted!")
