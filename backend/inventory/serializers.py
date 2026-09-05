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
    """
    O(1) stats cards — read straight off the InventoryStatsFlow singleton
    (or the merged dict from get_combined_inventory_stats, same shape).
    """
    total_products     = serializers.IntegerField(read_only=True)
    total_stock        = serializers.DecimalField(max_digits=20, decimal_places=4, read_only=True)
    low_stock_count    = serializers.IntegerField(read_only=True)
    out_of_stock_count = serializers.IntegerField(read_only=True)
    last_updated_at    = serializers.DateTimeField(read_only=True)


_REGISTRY_ID_PREFIX = {"raw_material": "rm", "wip_core": "wip", "wip_piece": "wip", "finished_goods": "fg"}


class CombinedInventoryRowSerializer(serializers.Serializer):
    """
    One row of the merged All Inventory view — now backed by a real
    ProductRegistryEntry queryset (see selectors.get_all_registry_products),
    not a Python-merged list of dicts. `id`/`product_id` are computed
    (SerializerMethodField) rather than plain model fields, so the wire
    format stays byte-for-byte identical to the old Python-merge version —
    zero frontend changes needed for this rewrite.
    """
    id               = serializers.SerializerMethodField()
    product_id       = serializers.SerializerMethodField()
    type             = serializers.ChoiceField(choices=["raw_material", "wip_core", "wip_piece", "finished_goods"])
    name             = serializers.CharField()
    code             = serializers.CharField(allow_null=True)
    category         = serializers.CharField(allow_null=True)
    quantity         = serializers.DecimalField(max_digits=14, decimal_places=4)
    # Can be NULL when the product's own Inventory/WipInventory/FgInventory
    # row doesn't exist yet (e.g. an RM variant created by a draft purchase
    # order that was never confirmed) — quantity itself is Coalesce'd to 0
    # for this case (see get_all_registry_products), but there's no
    # equally meaningful "zero" for a timestamp, so this stays nullable.
    last_updated_at  = serializers.DateTimeField(allow_null=True)

    def get_product_id(self, obj):
        return obj.rm_product_id or obj.wip_product_id or obj.fg_product_id

    def get_id(self, obj):
        # RM/WIP/FG products are independent auto-increment sequences that
        # can share numeric ids, and this is the row's React list key on
        # the frontend — namespaced, not a bare product id.
        return f"{_REGISTRY_ID_PREFIX[obj.type]}-{self.get_product_id(obj)}"


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
