from django.urls import reverse
import stripe
import time
from django.core.cache import cache
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
from base.serializers import CustomUserSerializer
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.mail import send_mail
import vonage
stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeCheckoutVIew(APIView):
    def post(self, request):
        data_package = [package for package in settings.ACTIVE_PRODUCTS]
        package = next(
            (pkg for pkg in data_package if pkg[0] == request.data['name_product']), None)

        if package is None:
            return Response({"error": "Invalid package name"}, status=status.HTTP_400_BAD_REQUEST)

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
            error_message = str(e)
            return Response({"error": error_message}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_successful(request, id):
    try:
        user_id = request.user.id
        user_object = CustomUser.objects.get(id=user_id)
        user_serializer = CustomUserSerializer(user_object)
        user_payment = UserPayment.objects.get(user=user_id)

        purchase_obj = Purchase.objects.get(
            payment_id=user_payment.purchase_id)

        serializer_purchase = PurchaseSerializer(purchase_obj)
        time.sleep(3)
        if user_payment.payment_bool is True:
            user_payment.stripe_checkout_id = id
            user_payment.save()

    except Exception as e:
        return Response(f'There has been an error: {e}')

    return Response({'purchase': serializer_purchase.data, 'user': user_serializer.data}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_cancelled(request):

    return Response('Payment cancelled response')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_purchases(request, id):
    try:
        user = request.user
        cache_key = f"purchases_for_user:{user.id}"
        # Try to fetch data from cache
        cached_data = cache.get(cache_key)
        if cached_data is None:
            user_payment = UserPayment.objects.get(user=user.id)
            purchase_obj = Purchase.objects.filter(userPayment=user_payment)
            serializer = PurchaseSerializer(purchase_obj, many=True)
            data = serializer.data
        else:
            data = cached_data['purchases']
    except Exception as e:
        return Response(f'There has been an error: {e}')

    return Response(data, status=status.HTTP_200_OK)


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
                user_obj.sms_count += package_obj.sms_count_pack
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
                    user_payment.purchase_id = event['data']['object']['payment_intent']
                    user_payment.payment_bool = False
                    user_payment.save()

                    # vonage_account_topup(package=package_obj.plan_typ)

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


@api_view(['POST'])
def calculate_plan_usage(request):
    BASIC_THRESHOLD_CUSTOMERS = 100
    SILVER_THRESHOLD_CUSTOMERS = 1000
    GOLD_THRESHOLD_CUSTOMERS = 5000

    BASIC_THRESHOLD_MESSAGES = 1000
    SILVER_THRESHOLD_MESSAGES = 2500
    GOLD_THRESHOLD_MESSAGES = 5000

    BASIC_THRESHOLD_BUDGET = 500
    SILVER_THRESHOLD_BUDGET = 1500
    GOLD_THRESHOLD_BUDGET = 3000

    try:
        messages_count = int(request.data.get('messages_count', 0))
        customers_count = int(request.data.get('customers_count', 0))
        budget = int(request.data.get('budget', 0))
        # is_business = bool(request.data.get('is_business', False))
        # Initialize scores for each package
        basic_score = 0
        silver_score = 0
        gold_score = 0

        # Evaluate based on the number of messages
        if messages_count <= BASIC_THRESHOLD_MESSAGES:
            basic_score += 1
        elif messages_count <= SILVER_THRESHOLD_MESSAGES:
            silver_score += 1
        else:
            gold_score += 1

        # Evaluate based on the number of customers
        if customers_count <= BASIC_THRESHOLD_CUSTOMERS:
            basic_score += 1
        elif customers_count <= SILVER_THRESHOLD_CUSTOMERS:
            silver_score += 1
        else:
            gold_score += 1

        # Evaluate based on the budget
        if budget <= BASIC_THRESHOLD_BUDGET:
            basic_score += 1
        elif budget <= SILVER_THRESHOLD_BUDGET:
            silver_score += 1
        else:
            gold_score += 1

        # Determine the recommended package
        if max(basic_score, silver_score, gold_score) == basic_score:
            return Response({'recommended_package': "BASIC PLAN"})
        elif max(basic_score, silver_score, gold_score) == silver_score:
            return Response({'recommended_package': "SILVER PLAN"})
        else:
            return Response({'recommended_package': "GOLD PLAN"})

    except Exception as e:
        return Response({'error': str(e)}, status=400)


def vonage_account_topup(package):
    try:
        vonage_client = vonage.Client(
            key=settings.VONAGE_ID, secret=settings.VONAGE_TOKEN)
        account = vonage.Account(vonage_client)
        if account:
            adjusted_amount = ammount_split(package)
        response = account.top_up(adjusted_amount)
        print(response)
        if response['status'] == '0':
            print("Top-up successful!")
        else:
            print(f"Top-up failed: {response['error-text']}")
    except Exception as e:
        print(f"Error topping up Vonage account: {e}")


def ammount_split(package: None):
    try:
        if package.plan_type == 'Gold package':
            return settings.GOLD_PACKAGE_AMOUNT
        elif package.plan_type == 'Silver package':
            return settings.SILVER_PACKAGE_AMOUNT
        elif package.plan_type == 'Basic package':
            return settings.BASIC_PACKAGE_AMOUNT
    except Exception as e:
        return e
