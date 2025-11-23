from rest_framework.serializers import ModelSerializer
from .models import Product, ProductScore



class ProductScoreSerializer(ModelSerializer):
    class Meta:
        model = ProductScore
        fields = "__all__"



class ProductSerializer(ModelSerializer):
    score = ProductScoreSerializer(read_only=True)
    class Meta:
        model = Product
        fields = '__all__'