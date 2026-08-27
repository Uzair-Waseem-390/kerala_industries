from rest_framework import serializers

from purchases.serializers import ProductLiteSerializer, ProductReadSerializer

from .models import Inventory, ShelfStock


class InventoryReadSerializer(serializers.ModelSerializer):
    product          = ProductReadSerializer(read_only=True)
    last_updated_by  = serializers.StringRelatedField(read_only=True)

    class Meta:
        model  = Inventory
        fields = ["id", "product", "quantity", "last_updated_at", "last_updated_by"]
        read_only_fields = fields


class InventoryStatsSerializer(serializers.Serializer):
    """O(1) stats cards — read straight off the InventoryStatsFlow singleton."""
    total_products     = serializers.IntegerField(read_only=True)
    low_stock_count    = serializers.IntegerField(read_only=True)
    out_of_stock_count = serializers.IntegerField(read_only=True)
    last_updated_at    = serializers.DateTimeField(read_only=True)


class ShelfStockReadSerializer(serializers.ModelSerializer):
    """
    Products + quantities currently on one shelf. Nests a lightweight
    product shape (id/name/code) rather than the full ProductReadSerializer
    — these rows are listed in bulk and don't need category/audit fields.
    """
    product = ProductLiteSerializer(read_only=True)

    class Meta:
        model  = ShelfStock
        fields = ["id", "product", "quantity", "last_updated_at"]
        read_only_fields = fields
