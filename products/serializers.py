from rest_framework.serializers import ModelSerializer
from .models import Product, ProductScore, ProductMedia, ProductMediaDraft, ProductDraft


class ProductScoreSerializer(ModelSerializer):
    class Meta:
        model = ProductScore
        fields = "__all__"



class ProductMediaSerializer(ModelSerializer):
    class Meta:
        model = ProductMedia
        fields = ["id", "shopify_media_id", "src", "alt_text"]

class ProductSerializer(ModelSerializer):
    score = ProductScoreSerializer(read_only=True)
    media = ProductMediaSerializer(source="productmedia_set", many=True, read_only=True)
    class Meta:
        model = Product
        fields = '__all__'


class ProductDraftMediaSerializer(ModelSerializer):
    class Meta:
        model = ProductMediaDraft
        fields = ["id", "shopify_media_id", "src", "alt_text"]

class ProductDraftSerializer(ModelSerializer):
    media = ProductDraftMediaSerializer(source="productmedia_set", many=True, read_only=True)
    class Meta:
        model = ProductDraft
        fields = '__all__'