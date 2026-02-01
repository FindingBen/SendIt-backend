from django.db import transaction
import logging
import stripe
import time
import vonage
from datetime import datetime, date
from django.conf import settings
from rest_framework.views import APIView
from .models import UserPayment, StripeEvent, Billing, Purchase
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import permission_classes, api_view
from rest_framework.response import Response
from django.db import transaction, IntegrityError
from base.utils.helpers import Utils
from django.http import HttpResponse
from rest_framework import status
from base.models import CustomUser, PackagePlan, AnalyticsData, ShopifyStore, Contact
from base.serializers import CustomUserSerializer, PackageSerializer
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.mail import send_mail
from notification.models import Notification
from base.shopify_functions import ShopifyFactoryFunction
from base.queries import CREATE_CHARGE, CURRENT_CHARGE, CANCEL_CHARGE, CREATE_PURCHASED_CHARGE,GET_CHARGE

stripe.api_key = settings.STRIPE_SECRET_KEY

util = Utils()
logger = logging.getLogger(__name__)

environment = settings.ENVIRONMENT

class ShopifyAuthMixin:
    """
    Reusable helper to resolve shopify store, token and graphql url from request headers.
    Raises ValueError on missing data so callers can return appropriate Response.
    """
    def resolve_shopify(self, request):
        shopify_domain = request.headers.get('shopify-domain', None)
        print(shopify_domain)
        if not shopify_domain:
            raise ValueError("Domain required from shopify!")
        try:

            shopify_store = ShopifyStore.objects.get(shop_domain=shopify_domain)

        except ShopifyStore.DoesNotExist:
            raise ValueError("Shopify store not found in local DB")
        auth = request.headers.get('Authorization', '')
        try:
            shopify_token = auth.split(' ')[1]
        except Exception:
            raise ValueError("Authorization header missing or malformed")
        url = f"https://{shopify_domain}/admin/api/{settings.SHOPIFY_API_VERSION}/graphql.json"
        return shopify_store, shopify_token, url

class StripeCheckoutSubscriptionView(APIView):
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
                mode='subscription',
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


class StripeCheckoutPurchaseView(APIView):
    def post(self, request):
        data_package = [package for package in settings.ACTIVE_PURCHASE_PRODUCTS]
        print("DATA", request.data)
        try:
            customer = CustomUser.objects.get(
                id=request.data['currentUser'])
        except Exception as e:
            return Response({"error": e}, status=status.HTTP_400_BAD_REQUEST)

        package = next(
            (pkg for pkg in data_package if pkg[0] == request.data['name_product']), None)
        print('PACKAGE', package)
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
                success_url=settings.DOMAIN_STRIPE_PURCHASE_NAME +
                '?success=true&session_id={CHECKOUT_SESSION_ID}',
                cancel_url=settings.DOMAIN_STRIPE_NAME_CANCEL + '/?cancel=true',
            )
            url_str = str(checkout_session.url)
            return Response({"url": url_str})

        except Exception as e:
            error_message = str(e)
            return Response({"error": error_message}, status=status.HTTP_400_BAD_REQUEST)

class StripeSubscriptionView(APIView):
    def post(self, request):
        pass


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def handle_stripe_subscription(request):
    try:
        session_id = request.data.get('session_id')
        user_payment = UserPayment.objects.get(user=request.user)
        custom_user = CustomUser.objects.get(id=request.user.id)

        if not session_id:
            return Response({'error': 'Session ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        stripe_session = stripe.checkout.Session.retrieve(session_id)
        if stripe_session.payment_status != 'paid':
            return Response({'error': 'Payment not completed.'}, status=status.HTTP_400_BAD_REQUEST)

        subscription_obj = stripe.Subscription.retrieve(
            id=user_payment.purchase_id)
        print(subscription_obj)
        return Response({'purchase': subscription_obj, 'user': CustomUserSerializer(custom_user).data}, status=status.HTTP_200_OK)

    except UserPayment.DoesNotExist:
        return Response({'error': 'Payment record not found.'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_stripe_subscription(request):
    try:
        util = Utils()
        user_id = request.user.id

        user = CustomUser.objects.get(id=user_id)

        user_payment = UserPayment.objects.get(user=user_id)
        trial_package = PackagePlan.objects.get(id=1)
        subscription_obj = stripe.Subscription.retrieve(
            id=user_payment.purchase_id)
        end_period = datetime.fromtimestamp(
            subscription_obj['current_period_end'])

        if subscription_obj['canceled_at'] is None:
            subscription = stripe.Subscription.modify(
                user_payment.purchase_id,
                cancel_at_period_end=True
            )
        else:
            return Response({'message': 'Subscription already cancelled!', 'subscription': subscription_obj}, status=status.HTTP_204_NO_CONTENT)

        print(subscription_obj)
        user.scheduled_subscription = None
        user.scheduled_package = None
        user.scheduled_cancel = end_period
        user.save()
        # recipients_qs = Contact.objects.filter(users=user)
        # flag_recipients = util.flag_recipients(user, recipients_qs)
        # if flag_recipients.get('was_downgraded', None) is True:
        #     user.downgraded = True
        #     user.save()
        return Response({'message': 'Subscription cancellation scheduled.', 'subscription': subscription_obj}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_shopify_subscription(request):
    try:
        util = Utils()
        user_id = request.user.id

        user = CustomUser.objects.get(id=user_id)

        
        trial_package = PackagePlan.objects.get(id=1)
        shopify_domain = request.headers.get('shopify-domain', None)
        if shopify_domain is None:
            return Response({'error': 'Shopify domain header is required'}, status=status.HTTP_400_BAD_REQUEST)
        url = f"https://{shopify_domain}/admin/api/{settings.SHOPIFY_API_VERSION}/graphql.json"
        shopify_token = request.headers['Authorization'].split(' ')[1]
        shopify_factory = ShopifyFactoryFunction(
                shopify_domain, shopify_token, url, request=request, query=CURRENT_CHARGE, headers=request.headers
            )
        response = shopify_factory.get_users_charge()
        data = response.json()
        if data.get("errors", {}):
                return Response(
                    {"error": "Url doesn't exist",
                        "details": data["errors"]["message"]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        plan_data = data.get('data', {}).get(
                'currentAppInstallation', {}
        ).get('activeSubscriptions', [])
        if not plan_data:
            return Response({"error": "No active subscription found to cancel."}, status=status.HTTP_404_NOT_FOUND)

        end_period = datetime.fromisoformat(
            plan_data[0].get('currentPeriodEnd').replace('Z', '+00:00'))
        subscription_id = plan_data[0]["id"] if plan_data and "id" in plan_data[0] else None

        shopify_factory = ShopifyFactoryFunction(
            shopify_domain, shopify_token, url, request=request, query=CANCEL_CHARGE, headers=request.headers
        )

        variable = {
            "id": subscription_id,
            "prorate": True
        }
        response = shopify_factory.cancel_recurring_charge(variable=variable)
        data = response.json()

        if data.get("errors", {}):
            return Response(
                {"error": "Url doesn't exist",
                    "details": data["errors"]["message"]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        cancel_data = data.get('data', {}).get('appSubscriptionCancel', {})
        if cancel_data.get('userErrors'):
            return Response({'error': cancel_data['userErrors']}, status=status.HTTP_400_BAD_REQUEST)
        subscription_obj = cancel_data.get('appSubscription', {})

        # if subscription_obj.get('status') == 'CANCELLED':
        #     return Response({'message': 'Subscription already cancelled!', 'subscription': subscription_obj}, status=status.HTTP_204_NO_CONTENT)

        user.scheduled_subscription = None
        user.scheduled_package = trial_package.plan_type
        user.scheduled_cancel = end_period
        user.save()
        return Response({'message': 'Subscription cancellation scheduled.', 'subscription': subscription_obj}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def payment_successful(request):
    try:
        user_id = request.user.id
        session_id = request.data.get('session_id')
        if not session_id:
            return Response({'error': 'Session ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        user_object = CustomUser.objects.get(id=user_id)
        user_serializer = CustomUserSerializer(user_object)
        user_payment = UserPayment.objects.get(user=user_id)

        # Retrieve the Stripe checkout session with line items expanded
        session = stripe.checkout.Session.retrieve(session_id, expand=['line_items'])
        print(session)
        if session.payment_status != 'paid':
            return Response({'error': 'Payment not completed.'}, status=status.HTTP_400_BAD_REQUEST)

        # Update user payment with checkout session ID
        user_payment.stripe_checkout_id = session_id
        user_payment.save()

        return Response({'purchase': session, 'user': user_serializer.data}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(f'There has been an error: {e}', status=status.HTTP_400_BAD_REQUEST)


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


SMS_PACKAGES = [
    {"sms_count": 200,"product_id": "prod_Ttl9MxlAsCFzyT"},
    {"sms_count": 1000,"product_id": "prod_Ttl9yN18YIuDR1"},
    {"sms_count": 5000,"product_id": "prod_Ttl9MM1aH2Cx7q"},
]

@require_http_methods(['POST'])
@csrf_exempt
def stripe_one_time_purchase_webhook(request):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    print('test')
    time.sleep(5)
    payload = request.body
    signature_header = request.META['HTTP_STRIPE_SIGNATURE']
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, signature_header, settings.STRIPE_PURCHASE_WEBHOOK_SECRET
        )

    except ValueError as e:
        print('ValueError:', e)
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        print('SignatureVerificationError:', e)
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
                ######
                print('ID', product_id)
                time.sleep(10)
                ######
                user_obj = CustomUser.objects.get(email=customer_email)
                print(user_obj)
                sms_object_package = next(
                    (pkg for pkg in SMS_PACKAGES if pkg["product_id"] == product_id), None)
                print('PACKAGE',sms_object_package)
                if sms_object_package is None:
                    print(f"No matching package for product_id: {product_id}")
                    return HttpResponse(status=400)
                user_obj.sms_count += sms_object_package['sms_count']
                user_obj.save()
                user_payment = UserPayment.objects.get(
                    user_id=user_obj.id)
                user_payment.purchase_id = payment_intent
                user_payment.payment_bool = True

                user_payment.save()
                if (user_payment.payment_bool == True):
                    user_payment.payment_bool = False
                    print('HERE7')
                    user_payment.stripe_checkout_id = session['id']
                    user_payment.save()
                    print('finally')
                analytics = AnalyticsData.objects.get(custom_user=user_obj.id)
                price = session.get('amount_total', 0) / 100  # Convert from cents to dollars
                analytics.total_spend += price
                analytics.save()
                StripeEvent.objects.create(event_id=event_id)
                send_mail(
                        subject=f'Receipt for sendperplane product SMS Credits ({sms_object_package["sms_count"]})',
                        message='Thank you for purchasing the package from us! We hope that you will enjoy our sending service.' +
                        '\n\n\n'
                        'Your purchase id is: ' +
                        f'{payment_intent}'', use that code to make an inquire in case you got any questions or issues during the payment.' +
                        '\n\n\n'
                        'Please dont hesitate to contact us at: support@sendperplane.com'+'\n'
                        'Once again, thank you for choosing Sendperplane. We look forward to serving you again in the future.' +
                        '\n\n'
                        'Best regards,'+'\n'
                        'Sendperplane team',
                        recipient_list=[customer_email],
                        from_email='support@sendperplane.com'
                    )
            except IntegrityError:
                pass
    return HttpResponse(status=200)

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
                payment_intent = session['subscription']
                print('PRODUCTION', session)
                ######
                time.sleep(10)
                ######
                user_obj = CustomUser.objects.filter(email=customer_email)[0]
                print('HERE')
                package_obj = PackagePlan.objects.get(id=product_id)
                user_obj.package_plan = package_obj
                user_obj.sms_count += package_obj.sms_count_pack
                user_obj.save()
                print('HERE1')
                user_payment = UserPayment.objects.get(
                    user_id=user_obj.id)
                print('HERE3')
                user_payment.purchase_id = payment_intent
                user_payment.payment_bool = True

                user_payment.save()
                print('HERE4')
                analytics = AnalyticsData.objects.get(custom_user=user_obj.id)
                analytics.total_spend += package_obj.price
                analytics.save()
                print('HERE6')
                if (user_payment.payment_bool == True):
                    user_payment.payment_bool = False
                    print('HERE7')
                    user_payment.stripe_checkout_id = session['id']
                    user_payment.save()
                    purchase_object = stripe.Subscription.retrieve(
                        id=user_payment.purchase_id
                    )
                    convert_epoch = datetime.fromtimestamp(
                        purchase_object['current_period_end'])

                    package_plan = PackagePlan.objects.get(
                        custom_id=purchase_object['plan']['product'])

                    user_obj.package_plan = package_plan
                    user_obj.sms_count = package_plan.sms_count_pack
                    user_obj.scheduled_subscription = convert_epoch
                    user_obj.scheduled_package = package_plan.plan_type

                    recipients_qs = Contact.objects.filter(users=user_obj)
                    flag_users = util.flag_recipients(
                        user_obj, recipients_qs)
                    user_obj.downgraded = not (
                        flag_users.get('was_downgraded') is False)

                    user_obj.save()
                    Notification.objects.create(
                        user=user_obj,
                        notif_type='success',
                        title="Purchase Successful",
                        message=f"Your purchase of {package_obj.plan_type} was successful!"
                    )
                    print('HERE8')
                    StripeEvent.objects.create(event_id=event_id)
                    print('HERE9')
                    send_mail(
                        subject=f'Receipt for sendperplane product {package_obj.plan_type}',
                        message='Thank you for purchasing the package from us! We hope that you will enjoy our sending service.' +
                        '\n\n\n'
                        'Your purchase id is: ' +
                        f'{event["data"]["object"]["subscription"]}'', use that code to make an inquire in case you got any questions or issues during the payment.' +
                        '\n\n\n'
                        'Please dont hesitate to contact us at: support@sendperplane.com'+'\n'
                        'Once again, thank you for choosing Sendperplane. We look forward to serving you again in the future.' +
                        '\n\n'
                        'Best regards,'+'\n'
                        'Sendperplane team',
                        recipient_list=[customer_email],
                        from_email='support@sendperplane.com'
                    )
                    print('HERE10')
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


@api_view(['GET'])
def get_shopify(request):
    try:
        print(request.headers)
        shopify_domain = request.headers.get('shopify-domain', None)
        print('DOMAIN',shopify_domain)
        if shopify_domain:
            shopify_token = request.headers['Authorization'].split(' ')[1]
            shopify_obj = ShopifyStore.objects.get(
                shop_domain=shopify_domain, access_token=shopify_token)
            if shopify_obj:
                return Response({
                    "is_shopify": True,
                }, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Shopify domain not provided"}, status=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        return Response({"error": "Shopify domain not provided"}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def create_shopify_charge(request):
    shopify_auth = ShopifyAuthMixin()
    shopify_token, shop, url = shopify_auth.resolve_shopify(request)
    plan = request.data.get("plan")  # e.g., basic, silver, gold
    # Define plan logic
    # data_package = [package for package in settings.ACTIVE_PRODUCTS_SHOPIFY]
    packages = settings.PROD_PRODUCTS_SHOPIFY
    return_url = "https://spplane.app" if environment == "production" else "http://localhost:3000"
    if packages is None:
        return Response({"error": "Invalid package name"}, status=status.HTTP_400_BAD_REQUEST)
    package_lookup = {pkg['plan_type']: pkg for pkg in packages}

    package = package_lookup.get(plan)

    charge_data = {"name": package["plan_type"],
                   "returnUrl": f"{return_url}/shopify/charge/confirmation?shop={shop}",
                   "lineItems": [
        {
            "plan": {
                "appRecurringPricingDetails": {
                    "price": {
                        "amount": package["price"],
                        "currencyCode": "USD"
                    },
                    "interval": "EVERY_30_DAYS"
                }
            }
        }
    ]
    }

    url = f"https://{shop}/admin/api/{settings.SHOPIFY_API_VERSION}/graphql.json"
    shopify_factory = ShopifyFactoryFunction(
        shop, shopify_token, url, request=request, query=CREATE_CHARGE)
    response = shopify_factory.create_reccuring_charge(variable=charge_data)
    data = response.json()
    print("SSSS", data)
    print(response)

    confirmation_url = data.get('data', {}).get(
        'appSubscriptionCreate', {}).get('confirmationUrl')
    return Response({"url": confirmation_url})

@api_view(['POST'])
def create_one_time_purchase_charge(request):
    shopify_auth = ShopifyAuthMixin()
    shop,shopify_token, url = shopify_auth.resolve_shopify(request)
    print(shopify_token)
    amount = request.data.get("amount")
    description = request.data.get("description", "One-time purchase 200 credits")

    return_url = "https://spplane.app" if environment == "production" else "http://localhost:3000"
    charge_data = {
        "name": description,
        "price": {
            "amount": amount,
            "currencyCode": "USD"
        },
        "returnUrl": f"{return_url}/shopify/one_time_charge/confirmation?shop={shop.shop_domain}"
    }

    shopify_factory = ShopifyFactoryFunction(
        shop.shop_domain, shopify_token, url, request=request, query=CREATE_PURCHASED_CHARGE)
    response = shopify_factory.create_one_time_purchase_charge(variable=charge_data)
    data = response.json()
    print("RAW SHOPIFY RESPONSE:", data)

    errors = data.get("data", {}).get("appPurchaseOneTimeCreate", {}).get("userErrors")
    if errors:
        return Response({"errors": errors}, status=400)
    confirmation_url = data.get('data', {}).get(
        'appPurchaseOneTimeCreate', {}).get('confirmationUrl')
    return Response({"url": confirmation_url})

SMS_AMOUNTS = {
    "200 sms": 200,
    "1000 sms": 1000,
    "5000 sms": 5000,
}

@api_view(["GET"])
def check_one_time_charge(request):
    shopify_auth = ShopifyAuthMixin()
    shop, shopify_token, url = shopify_auth.resolve_shopify(request)

    charge_id = request.GET.get("charge_id")
    if not charge_id:
        return Response({"error": "Missing charge_id"}, status=400)

    # Convert numeric ID → Shopify GID
    gid = f"gid://shopify/AppPurchaseOneTime/{charge_id}"

    shopify_factory = ShopifyFactoryFunction(
        shop.shop_domain,
        shopify_token,
        url,
        request=request,
        query=GET_CHARGE,
    )

    response = shopify_factory.get_charge(gid)
    data = response.json()

    node = data.get("data", {}).get("node")
    if not node:
        return Response({"error": "Charge not found"}, status=400)

    # 🔐 SECURITY CHECKS
    if node["status"] != "ACTIVE":
        return Response({"error": "Charge not active"}, status=400)

    package_name = node["name"]
    sms_amount = SMS_AMOUNTS.get(package_name)

    if not sms_amount:
        return Response({"error": "Unknown SMS package"}, status=400)

    user_obj = CustomUser.objects.get(email=shop.email)
    user_payment = UserPayment.objects.get(user=user_obj)


    # 🔒 Idempotent transaction
    with transaction.atomic():
        if Purchase.objects.filter(payment_id=gid).exists():
            return Response(
                {"status": "Already processed"},
                status=status.HTTP_208_ALREADY_REPORTED,
            )

        # ✅ Append credits
        user_obj.sms_count += sms_amount
        user_obj.save(update_fields=["sms_count"])

        # ✅ Record purchase
        Purchase.objects.create(
            userPayment=user_payment,
            package_name=package_name,
            price=int(node.get("price", {}).get("amount", 0)) if node.get("price") else 0,
            payment_method="shopify",
            payment_id=gid,
        )

    return Response(
        {
            "status": "Credits applied",
            "sms_added": sms_amount,
            "total_sms": user_obj.sms_count,
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
def check_users_charge(request):
    try:
        shopify_domain = request.headers.get('shopify-domain', None)
        url = f"https://{shopify_domain}/admin/api/{settings.SHOPIFY_API_VERSION}/graphql.json"
        charge_id = request.GET.get('charge_id', None)

        if shopify_domain:
            shopify_token = request.headers['Authorization'].split(' ')[1]
            shopify_obj = ShopifyStore.objects.get(
                shop_domain=shopify_domain, access_token=shopify_token)
            user_obj = CustomUser.objects.get(custom_email=shopify_obj.email)
            if Billing.objects.filter(shopify_charge_id=charge_id, user=user_obj).exists() or charge_id is None:
                return Response({
                    "package": "Data already returned",
                    "status": 208
                }, status=status.HTTP_208_ALREADY_REPORTED)
            shopify_factory = ShopifyFactoryFunction(
                shopify_domain, shopify_token, url, request=request, query=CURRENT_CHARGE, headers=request.headers
            )
            response = shopify_factory.get_users_charge()
            data = response.json()

            if data.get("errors", {}):
                return Response(
                    {"error": "Url doesn't exist",
                        "details": data["errors"]["message"]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            plan_data = data.get('data', {}).get(
                'currentAppInstallation', {}
            ).get('activeSubscriptions', [])
            if len(plan_data) > 0:
                plan_info = plan_data[0]
            else:
                return Response({"error": "No active subscription found"}, status=status.HTTP_404_NOT_FOUND)
            shopify_charge_id = plan_info.get('id')
            charge_number = shopify_charge_id.split('/')[-1]

            billing_amount = float(
                plan_info['lineItems'][0]['plan']['pricingDetails']['price']['amount'])
            billing_status = plan_info.get('status', 'pending')
            billing_plan = plan_info.get('name', 'None')
            next_billing_date_str = plan_info.get(
                'currentPeriodEnd')
            next_billing_date = datetime.fromisoformat(
                next_billing_date_str.replace('Z', '+00:00')).date()

            package_obj = PackagePlan.objects.get(plan_type=billing_plan)
            util = Utils(shopify_domain)

            # Check if user already has an active plan
            if user_obj.scheduled_subscription is None or user_obj.scheduled_subscription <= date.today():
                # First-time plan assignment
                with transaction.atomic():
                    Billing.objects.create(
                        user=user_obj,
                        billing_amount=billing_amount,
                        billing_plan=billing_plan,
                        billing_status=billing_status,
                        shopify_charge_id=charge_number
                    )
                    logger.info('Activating plan for user')
                    user_obj.package_plan = package_obj
                    # user_obj.sms_count = package_obj.sms_count_pack
                    user_obj.scheduled_subscription = next_billing_date
                    user_obj.scheduled_package = billing_plan
                    user_obj.save()
                    analytics = AnalyticsData.objects.get(
                        custom_user=user_obj.id)
                    analytics.total_spend += package_obj.price
                    analytics.save()

                package_data = PackageSerializer(package_obj).data
                limits = util.get_package_limits(user_obj.package_plan)

                return Response({
                    "package": package_data,
                    "limits": limits,
                    "info": "Plan activated immediately."
                }, status=status.HTTP_200_OK)
            else:
                user_obj.scheduled_subscription = next_billing_date
                user_obj.scheduled_package = billing_plan
                user_obj.save()
                package_data = PackageSerializer(package_obj).data
                limits = util.get_package_limits(user_obj.package_plan)

                return Response({
                    "scheduled_package": "Plan subscription triggered!",
                    "scheduled_date": next_billing_date,
                    "info": f"Plan scheduled to activate on {next_billing_date}."
                }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_billings(request):
    try:
        user_obj = CustomUser.objects.get(
            id=request.user.id)
        # Get latest 5 billings for this user
        billings = Billing.objects.filter(
            user=user_obj).order_by('-billing_date')[:5]
        billing_list = [
            {
                "billing_date": billing.billing_date,
                "billing_amount": billing.billing_amount,
                "billing_status": billing.billing_status,
                "billing_plane": billing.billing_plan,
                "shopify_charge_id": billing.shopify_charge_id,
            }
            for billing in billings
        ]
        return Response({"billings": billing_list}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
