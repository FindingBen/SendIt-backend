from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .models import Sms
from base.models import Message, ContactList
from base.serializers import MessageSerializer
from .serializers import SmsSerializer
from rest_framework import generics


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_message(request, id):
    message = Message.objects.get(id=id)
    # contact = Message.objects.filter(contact_list=contact_list)
    serializer = MessageSerializer(message)

    if serializer.is_valid():

        return Response(serializer.data, status=status.HTTP_200_OK)

    else:

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class createSms(generics.GenericAPIView):
    serializer_class = SmsSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sms = serializer.save()
        return Response({
            "sms": SmsSerializer(sms, context=self.get_serializer_context()).data
        })
