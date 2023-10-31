import stripe
import time
from django.conf import settings
from rest_framework.views import APIView
from .models import UserPayment, Purchase
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import permission_classes, api_view
from rest_framework.response import Response
from .serializers import PurchaseSerializer
from django.db import transaction, IntegrityError
from django.http import HttpResponse
from rest_framework import status
from base.models import CustomUser, PackagePlan
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeCheckoutVIew(APIView):
    def post(self, request):
        data_package = [package for package in settings.ACTIVE_PRODUCTS]

        package = next(
            (pkg for pkg in data_package if pkg[0] == request.data['name_product']), None)

        if package is None:
            return Response({"error": "Invalid package name"})
        print(settings.ACTIVE_PRODUCTS)

        # try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    # Provide the exact Price ID (for example, pr_1234) of the product you want to sell
                    'price': package[1],
                    'quantity': 1,
                },

            ],
            metadata={
                'product_id': package[2],

            },

            payment_method_types=['card'],
            mode='payment',
            success_url=settings.DOMAIN_STRIPE_NAME + \
            '/?success=true&session_id={CHECKOUT_SESSION_ID}',
            cancel_url=settings.DOMAIN_STRIPE_NAME_CANCEL + '/?cancel=true',
        )

        url_str = str(checkout_session.url)
        return Response({"url": url_str})

        # except Exception as e:

        #     error_message = str(e)  # Get the error message as a string
        #     return Response({"error": error_message})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_successful(request, id):

    user_id = request.user

    user_payment = UserPayment.objects.get(user=user_id)
    print('success_payment', user_id)
    user_payment.stripe_checkout_id = id
    user_payment.save()
    return Response('Successfull response')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_cancelled(request):

    return Response('Payment cancelled response')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_purchases(request, id):
    user_id = request.user
    print('success?', user_id)
    user_payment = UserPayment.objects.get(user=user_id)
    purchase_obj = Purchase.objects.filter(userPayment=user_payment)
    serializer = PurchaseSerializer(purchase_obj, many=True)
    print('success?', user_payment)
    return Response(serializer.data, status=status.HTTP_200_OK)


@require_http_methods(['POST'])
@csrf_exempt
def stripe_webhook(request):

    stripe.api_key = settings.STRIPE_SECRET_KEY

    time.sleep(5)
    payload = request.body
    signature_header = request.META['HTTP_STRIPE_SIGNATURE']
    event = None
    try:
        event = stripe.Webhook.construct_event(
            payload, signature_header, settings.STRIPE_WEBHOOK_SECRET
        )

    except ValueError as e:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        return HttpResponse(status=400)

    if event['type'] == 'checkout.session.completed':

        with transaction.atomic():
            try:
                session = event['data']['object']
                session_id = session.get('id', None)
                customer_email = session["customer_details"]["email"]
                product_id = session["metadata"]["product_id"]

                time.sleep(10)

                user_payment = UserPayment.objects.get(
                    stripe_checkout_id=session_id)
                print('payment?', user_payment)
                user_payment.payment_bool = True
                user_payment.save()

                user_obj = CustomUser.objects.filter(email=customer_email)[0]
                package_obj = PackagePlan.objects.get(id=product_id)

                user_obj.package_plan = package_obj
                user_obj.save()

                payment_type_details = event['data']['object'].get(
                    'payment_method_types')
                print('test3')
                if (user_payment.payment_bool == True):
                    time.sleep(10)
                    payment_type_details = event['data']['object'].get(
                        'payment_method_types')
                    create_purchase = Purchase(userPayment=user_payment,
                                               package_name=package_obj.plan_type,
                                               price=package_obj.price,
                                               payment_id=event['data']['object']['payment_intent'],
                                               payment_method=payment_type_details)
                    create_purchase.save()
                    user_payment.payment_bool = False
                    user_payment.save()
                    print(user_payment)
            except IntegrityError:
                pass

    return HttpResponse(status=200)
