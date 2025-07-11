from django.urls import reverse
import stripe
import time
from datetime import datetime
from django.core.cache import cache
from django.conf import settings
from rest_framework.views import APIView
from .models import UserPayment, StripeEvent
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import permission_classes, api_view
from rest_framework.response import Response
from .serializers import PurchaseSerializer
from django.db import transaction, IntegrityError
from django.http import HttpResponse
from rest_framework import status
from base.models import CustomUser, PackagePlan, AnalyticsData
from base.serializers import CustomUserSerializer
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.mail import send_mail
from notification.models import Notification
import vonage
stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeCheckoutVIew(APIView):
    def post(self, request):
        data_package = [package for package in settings.ACTIVE_PRODUCTS]

        try:
            customer = CustomUser.objects.get(
                id=request.data['currentUser'])

        except Exception as e:
            return Response({"error": e}, status=status.HTTP_400_BAD_REQUEST)

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
                customer=customer.stripe_custom_id,
                success_url=settings.DOMAIN_STRIPE_NAME +
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

        purchase_object = stripe.PaymentIntent.retrieve(
            id=user_payment.purchase_id)

        # purchase_obj = Purchase.objects.get(
        #     payment_id=user_payment.purchase_id)
        # print("PURCHASE")
        # serializer_purchase = PurchaseSerializer(purchase_obj)
        time.sleep(3)
        if user_payment.payment_bool is True:
            user_payment.stripe_checkout_id = id
            user_payment.save()
            print('FINAL STAGE')
    except Exception as e:
        return Response(f'There has been an error: {e}')

    return Response({'purchase': purchase_object, 'user': user_serializer.data}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_cancelled(request):

    return Response('Payment cancelled response')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_purchases(request, id):
    try:
        print(request.user)
        # Ensure the user is authorized to fetch this data
        user = request.user
        # if user.id != id:
        #     return Response({"error": "Unauthorized access"}, status=status.HTTP_403_FORBIDDEN)

        # Get the Stripe customer ID linked to the user
        customer = CustomUser.objects.get(id=user.id)
        if not customer.stripe_custom_id:
            return Response({"error": "No Stripe customer linked to this user"}, status=status.HTTP_404_NOT_FOUND)

        # Fetch transactions for the specific customer
        transactions = stripe.PaymentIntent.list(
            customer=customer.stripe_custom_id)
        print(customer.stripe_custom_id)
        # Parse transactions into response format
        transaction_data = []
        for transaction in transactions['data']:
            transac_dict_obj = {
                "payment_id": transaction.id,
                "price": transaction.amount,
                "type": transaction.payment_method_types[0],
                "created_at": datetime.fromtimestamp(transaction.created).strftime('%Y-%m-%d %H:%M:%S'),
                "status": transaction.status
            }
            transaction_data.append(transac_dict_obj)

        # Apply optional search and sorting
        search_query = request.GET.get('search', None)
        if search_query:
            transaction_data = [
                transaction for transaction in transaction_data
                if search_query.lower() in transaction['payment_id'].lower()
            ]

        sort_order = request.GET.get('sort_order', 'asc')  # Default ascending
        reverse = sort_order == 'desc'
        transaction_data.sort(key=lambda x: x['created_at'], reverse=reverse)

        return Response(transaction_data, status=status.HTTP_200_OK)

    except CustomUser.DoesNotExist:
        return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


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

    event_id = event['id']
    if StripeEvent.objects.filter(event_id=event_id).exists():
        return HttpResponse(status=200)

    if event['type'] == 'checkout.session.completed':

        with transaction.atomic():
            try:
                session = event['data']['object']
                customer_email = session["customer_details"]["email"]
                product_id = session["metadata"]["product_id"]
                payment_intent = session['payment_intent']
                print('PRODUCTION', session)
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
                user_payment.purchase_id = payment_intent
                user_payment.payment_bool = True

                user_payment.save()
                analytics = AnalyticsData.objects.get(custom_user=user_obj.id)
                analytics.total_spend += package_obj.price
                analytics.save()
                if (user_payment.payment_bool == True):
                    user_payment.payment_bool = False

                    user_payment.save()
                    Notification.objects.create(
                        user=user_obj,
                        notif_type='success',
                        title="Purchase Successful",
                        message=f"Your purchase of {package_obj.plan_type} was successful!"
                    )
                    StripeEvent.objects.create(event_id=event_id)
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
                    Notification.objects.create(
                        user=user_obj,
                        notif_type='error',
                        title="Purchase Not completed",
                        message=f"Your purchase of {package_obj.plan_type} was not completed, contact support!"
                    )
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
            return Response({'recommended_package': "BASIC PACKAGE"})
        elif max(basic_score, silver_score, gold_score) == silver_score:
            return Response({'recommended_package': "SILVER PACKAGE"})
        else:
            return Response({'recommended_package': "GOLD PACKAGE"})

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
