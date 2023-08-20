from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .models import Sms
from base.models import Message, ContactList, CustomUser
from base.serializers import MessageSerializer
from .serializers import SmsSerializer
from rest_framework import generics


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_message(request, id):
    message = Message.objects.get(id=id)
    # contact = Message.objects.filter(contact_list=contact_list)
    serializer = MessageSerializer(message)

    # if serializer.is_valid(raise_exception=True):

    return Response(serializer.data, status=status.HTTP_200_OK)


class createSms(generics.GenericAPIView):
    serializer_class = SmsSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        print(request.data)
        user_obj = CustomUser.objects.get(id=request.data['user'])
        if user_obj.sms_count > 0:
            print('ssdasds')
            if serializer.is_valid():
                sms = serializer.save()
                print('ss')
                return Response({
                    "sms": SmsSerializer(sms, context=self.get_serializer_context()).data
                })
        else:
            return Response({'error': 'You have no sms credit left, purchase a new package or extend the current one'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
