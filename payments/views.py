import stripe
import time
from django.conf import settings
from rest_framework.views import APIView
from .models import UserPayment
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import permission_classes, api_view
from rest_framework.response import Response
from django.db import transaction, IntegrityError
from django.http import HttpResponse
from base.models import CustomUser, PackagePlan
from django.views.decorators.csrf import csrf_exempt


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
                success_url=settings.DOMAIN_NAME + \
                '/?success=true&session_id={CHECKOUT_SESSION_ID}',
                cancel_url=settings.DOMAIN_NAME_CANCEL + '/?cancel=true',
            )
            return Response({"url": checkout_session.url})

        except Exception as e:
            return


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_successful(request, id):
    stripe.api_key = settings.STRIPE_SECRET_KEY

    user_id = request.user

    user_payment = UserPayment.objects.get(user=user_id)
    user_payment.stripe_checkout_id = id
    user_payment.save()
    return Response('Successfull response')


@csrf_exempt
def stripe_webhook(request):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    time.sleep(2)
    payload = request.body
    signature_header = request.META['HTTP_STRIPE_SIGNATURE']
    event = None
    try:
        event = stripe.Webhook.construct_event(
            payload, signature_header, settings.STRIPE_WEBHOOK_SECRET
        )
        print(event['data']['object'])
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
                user_payment.payment_bool = True
                user_payment.save()

                user_obj = CustomUser.objects.filter(email=customer_email)[0]
                package_obj = PackagePlan.objects.get(id=product_id)

                user_obj.package_plan = package_obj
                user_obj.save()

            except IntegrityError:
                pass

    return HttpResponse(status=200)
