from rest_framework import serializers

from .models import Bundle, BundleCategory, BundleItem


class BundleCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BundleCategory
        fields = ("id", "name", "type", "category_filters")


class BundleItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = BundleItem
        fields = ("id", "bundle", "item")


class BundleSerializer(serializers.ModelSerializer):
    bundle_items = BundleItemSerializer(many=True, read_only=True)

    class Meta:
        model = Bundle
        fields = ("id", "bundle_category", "name", "discount_pct", "status", "bundle_items", "created_at")
