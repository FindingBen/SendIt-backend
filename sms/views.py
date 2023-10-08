from django.shortcuts import render, get_object_or_404
from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .models import Sms
from django.views.decorators.csrf import csrf_exempt
from base.models import Message, ContactList, CustomUser
from base.serializers import MessageSerializer
from .serializers import SmsSerializer
from rest_framework import generics
from django.http import JsonResponse
from django.http import HttpResponseRedirect, HttpResponse
import jwt
from django.db import transaction
import hashlib


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_message(request, id):
    message = Message.objects.get(id=id)
    # contact = Message.objects.filter(contact_list=contact_list)
    serializer = MessageSerializer(message)

    # if serializer.is_valid(raise_exception=True):

    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_sms(request, id):
    sms = Sms.objects.get(message_id=id)

    serializer = SmsSerializer(sms)

    return Response(serializer.data, status=status.HTTP_200_OK)


class createSms(generics.GenericAPIView):
    serializer_class = SmsSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_obj = CustomUser.objects.get(id=request.data['user'])
        if user_obj.sms_count > 0:
            if serializer.is_valid():

                sms = serializer.save()

                return Response({
                    "sms": SmsSerializer(sms, context=self.get_serializer_context()).data
                })
        else:
            return Response({'error': 'You have no sms credit left, purchase a new package or extend the current one'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)


def track_link_click(request, uuid):

    sms_obj = Sms.objects.get(unique_tracking_id=uuid)

    message_obj = Message.objects.get(id=sms_obj.message.id)

    sms_obj.click_number += 1  # Increment click_number by 1
    sms_obj.save()

    # # Return a JSON response indicating that the click was recorded
    # # Replace with your desired URL
    redirect_url = f"https://sendit-frontend-production.up.railway.app/message_view/{message_obj.id}"
    return HttpResponseRedirect(redirect_url)


@csrf_exempt
@api_view(['POST'])
def vonage_webhook(request):
    try:
        # Parse the JSON data from the request body
        data = request.data
        sms_object = Sms.objects.get(unique_tracking_id=data['client-ref'])
        with transaction.atomic():
            if data['status'] == 'delivered':
                sms_object.delivered += 1

            elif data['status'] == 'failed':
                sms_object.not_delivered += 1
            elif data['status'] == 'rejected':
                sms_object.not_delivered += 1

            sms_object.save()

        print('Received Vonage Delivery Receipt:')

        # Respond with a success message
        return JsonResponse({'message': 'Delivery receipt received successfully'}, status=200)

    except Exception as e:
        print('Error handling Vonage delivery receipt:', str(e))

        return JsonResponse({'error': 'Error processing delivery receipt'}, status=500)
