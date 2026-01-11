from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.conf import settings
from base.models import ShopifyStore
from products.models import Product
from django.db import transaction
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .models import Notification, OptimizationJob
from .serializers import NotificationSerializer, OptimizationJobSerializer
from products.tasks import start_optimization_task

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


class NotificationView(APIView,ShopifyAuthMixin):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, notification_id=None):
        """
        - If notification_id is provided → return that notification
        - Otherwise → return last 4 notifications for the user
        """
        if notification_id:
            try:
                notif = Notification.objects.get(id=notification_id, user=request.user)
            except Notification.DoesNotExist:
                return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

            serializer = NotificationSerializer(notif)
            return Response(serializer.data)

        # Default: return all notifications (or limit as needed)
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:20]
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = NotificationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        notif_id = request.data.get('id')
        if not notif_id:
            return Response({'error': 'Notification id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            notification = Notification.objects.get(
                id=notif_id, user=request.user)
            notification.read = True
            notification.save()
            serializer = NotificationSerializer(notification)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Notification.DoesNotExist:
            return Response({'error': 'Notification not found.'}, status=status.HTTP_404_NOT_FOUND)


class OptimizationJobView(APIView, ShopifyAuthMixin):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        jobs = OptimizationJob.objects.filter(user=user).order_by('-created_at')
        serializer = OptimizationJobSerializer(jobs, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        try:
            shopify_store, shopify_token, url = ShopifyAuthMixin().resolve_shopify(request)
            data = request.data
            print('DATA RECEIVED:', data)
            if not can_optimize(shopify_store):
                return Response({
                    "error": "Maximum concurrent optimizations reached."
                }, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
            product = Product.objects.get(product_id=data['product_id'])
            
            #with transaction.atomic():
            job = OptimizationJob.objects.create(
            user=request.user,
            product_id=data['product_id'],
            store=shopify_store,
            status="pending",
            )
            print('CREATED',job)
            product.optimization_status = "in progress"
            product.save(update_fields=["optimization_status"])
            
            start_optimization_task.apply_async(args=[str(job.id)])
            
            return Response({
                "job_id": str(job.id),
                "status": "started"
            },status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            print('ERROR CREATING OPTIMIZATION JOB:', str(e))
            return Response({
                "error": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        
def can_optimize(store):
    return OptimizationJob.objects.filter(
                    store=store,
                    status__in=["pending", "failed", "completed"],
    ).count() < int(settings.MAX_OPTIMIZATIONS)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def optimization_quota(request):
    try:
        shopify_store, shopify_token, url = ShopifyAuthMixin().resolve_shopify(request)
        used = OptimizationJob.objects.filter(
            store=shopify_store,
            status__in=["queued", "running", "completed"],
        ).count()

        return Response({
            "used": used,
            "limit": 50,
            "remaining": max(0, 50 - used),
        })
    except ValueError as ve:
        return Response({
            "error": str(ve)
        }, status=status.HTTP_400_BAD_REQUEST)
