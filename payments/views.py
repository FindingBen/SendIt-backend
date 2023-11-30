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
from django.core.mail import send_mail
stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeCheckoutVIew(APIView):
    def post(self, request):
        data_package = [package for package in settings.ACTIVE_PRODUCTS]

        package = next(
            (pkg for pkg in data_package if pkg[0] == request.data['name_product']), None)

        if package is None:
            return Response({"error": "Invalid package name"})

        try:
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

        except Exception as e:

            error_message = str(e)  # Get the error message as a string
            return Response({"error": error_message})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_successful(request, id):
    try:
        user_id = request.user
        user_payment = UserPayment.objects.get(user=user_id.id)
        user_payment.stripe_checkout_id = id
        user_payment.save()
    except Exception as e:
        return Response(f'There has been an error: {e}')

    return Response('Successfull response')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_cancelled(request):

    return Response('Payment cancelled response')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_purchases(request, id):
    try:
        user_id = request.user
        user_payment = UserPayment.objects.get(user=user_id.id)
        purchase_obj = Purchase.objects.filter(userPayment=user_payment)
        serializer = PurchaseSerializer(purchase_obj, many=True)
    except Exception as e:
        return Response(f'There has been an error: {e}')

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
                customer_email = session["customer_details"]["email"]
                product_id = session["metadata"]["product_id"]
                ######
                time.sleep(10)
                ######
                user_obj = CustomUser.objects.filter(email=customer_email)[0]
                package_obj = PackagePlan.objects.get(id=product_id)
                user_obj.package_plan = package_obj
                user_obj.save()
                user_payment = UserPayment.objects.get(
                    user_id=user_obj.id)
                user_payment.payment_bool = True
                user_payment.save()

                if (user_payment.payment_bool == True):
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
                    send_mail(
                        subject=f'Receipt for sendperplane product {package_obj.plan_type}',
                        message='Thank you for purchasing the package from us! We hope that you will enjoy our sending service.' +
                        '\n\n\n'
                        'Your purchase id is: ' +
                        f'{event["data"]["object"]["payment_intent"]}'', use that code to make an inquire in case you got any questions or issues during the payment.' +
                        '\n\n\n'
                        'Please dont hesitate to contact us at: beniagic@gmail.com'+'\n'
                        'Once again, thank you for choosing Sendperplane. We look forward to serving you again in the future.' +
                        '\n\n'
                        'Best regards,'+'\n'
                        'Sendperplane team',
                        recipient_list=[customer_email],
                        from_email='benarmys4@gmail.com'
                    )
                else:
                    return Response('Payment not completed! Contact administrator for more info')
            except IntegrityError:
                pass

    return HttpResponse(status=200)
