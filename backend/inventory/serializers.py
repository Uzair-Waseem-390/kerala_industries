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


class CombinedInventoryRowSerializer(serializers.Serializer):
    """
    One row of the merged All Inventory view — RM and WIP products
    normalized into a common shape (see selectors.get_combined_inventory_rows).
    Plain Serializer, not ModelSerializer: the source is a list of dicts,
    not a queryset of one model.
    """
    # Namespaced string ("rm-14"/"wip-14"), not a bare product id — RM and
    # WIP products are independent auto-increment sequences that can share
    # numeric ids, and this is the row's React list key on the frontend.
    id               = serializers.CharField()
    type             = serializers.ChoiceField(choices=["raw_material", "wip_core", "wip_piece"])
    name             = serializers.CharField()
    code             = serializers.CharField(allow_null=True)
    category         = serializers.CharField(allow_null=True)
    quantity         = serializers.DecimalField(max_digits=14, decimal_places=4)
    last_updated_at  = serializers.DateTimeField()


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
