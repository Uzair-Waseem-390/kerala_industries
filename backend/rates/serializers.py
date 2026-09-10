from rest_framework import serializers

from .models import ProductRate, ProductRateHistory


# ---------------------------------------------------------------------------
# ProductRateHistory serializer (read-only — append-only model)
# ---------------------------------------------------------------------------

class ProductRateHistorySerializer(serializers.ModelSerializer):
    changed_by = serializers.StringRelatedField(read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)

    class Meta:
        model = ProductRateHistory
        fields = [
            "id", "product_name", "product_code",
            "selling_price", "changed_by", "changed_at", "note",
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# ProductRate read serializer — `product` is either an RM (Cartons-family)
# or FG product; picked at serialize time since ProductRate.product is a
# Python property over two nullable FKs, not a single relation a nested
# ModelSerializer field can point at directly.
# ---------------------------------------------------------------------------

class ProductRateReadSerializer(serializers.ModelSerializer):
    product      = serializers.SerializerMethodField()
    product_type = serializers.SerializerMethodField()
    updated_by   = serializers.StringRelatedField(read_only=True)
    created_by   = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = ProductRate
        fields = [
            "id", "product", "product_type", "selling_price",
            "created_by", "updated_by", "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_product_type(self, obj):
        return "fg" if obj.fg_product_id else "rm"

    def get_product(self, obj):
        if obj.fg_product_id:
            from production.serializers import FgProductReadSerializer
            return FgProductReadSerializer(obj.fg_product).data
        from purchases.serializers import ProductReadSerializer
        return ProductReadSerializer(obj.rm_product).data


# ---------------------------------------------------------------------------
# ProductRate write serializers — separate for create vs update (DRY via base)
# ---------------------------------------------------------------------------

class ProductRateBaseWriteSerializer(serializers.Serializer):
    """
    Shared fields between create and update.
    Declared as a plain Serializer (not ModelSerializer) so both
    create and update serializers can inherit without model conflicts.
    """
    selling_price = serializers.DecimalField(max_digits=14, decimal_places=4)
    note = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        default="",
        help_text="Optional reason for price change.",
    )

    def validate_selling_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Selling price must be greater than zero.")
        return value


class ProductRateCreateSerializer(ProductRateBaseWriteSerializer):
    """Used for POST — requires exactly one of rm_product_id/fg_product_id."""
    rm_product_id = serializers.IntegerField(required=False, allow_null=True)
    fg_product_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        rm_id = attrs.get("rm_product_id")
        fg_id = attrs.get("fg_product_id")
        if bool(rm_id) == bool(fg_id):
            raise serializers.ValidationError({"product": "Exactly one of rm_product_id or fg_product_id is required."})
        if rm_id:
            from purchases.models import Product
            if not Product.objects.filter(pk=rm_id, is_deleted=False).exists():
                raise serializers.ValidationError({"rm_product_id": "Product not found or has been deleted."})
        if fg_id:
            from production.models import FgProduct
            if not FgProduct.objects.filter(pk=fg_id, is_deleted=False).exists():
                raise serializers.ValidationError({"fg_product_id": "Product not found or has been deleted."})
        return attrs


class ProductRateUpdateSerializer(ProductRateBaseWriteSerializer):
    """Used for PATCH — only selling_price + note, product is immutable."""
    pass
