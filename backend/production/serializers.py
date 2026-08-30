from decimal import Decimal

from rest_framework import serializers

from purchases.serializers import ShelfAllocationInputSerializer

from .models import (
    Recipe, RecipeBreakdownItem, RecipeIssuedMaterial, RecipeMaterialConsumption,
    RewoundCoreBinding, RewoundCoreLengthMm, RewoundCoreYard, WipInventory, WipProduct,
)


class AuditReadMixin(serializers.Serializer):
    created_by = serializers.StringRelatedField(read_only=True)
    updated_by = serializers.StringRelatedField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


# ---------------------------------------------------------------------------
# WIP attribute lookups (Rewinding) — read-only from the API's perspective;
# rows are created as a side effect of add_breakdown_item, never directly.
# ---------------------------------------------------------------------------

class RewoundCoreBindingReadSerializer(AuditReadMixin, serializers.ModelSerializer):
    class Meta:
        model  = RewoundCoreBinding
        fields = ["id", "value", "created_by", "updated_by", "created_at", "updated_at"]


class RewoundCoreYardReadSerializer(AuditReadMixin, serializers.ModelSerializer):
    class Meta:
        model  = RewoundCoreYard
        fields = ["id", "value", "created_by", "updated_by", "created_at", "updated_at"]


class RewoundCoreLengthMmReadSerializer(AuditReadMixin, serializers.ModelSerializer):
    class Meta:
        model  = RewoundCoreLengthMm
        fields = ["id", "value", "created_by", "updated_by", "created_at", "updated_at"]


# ---------------------------------------------------------------------------
# WIP Product / Inventory
# ---------------------------------------------------------------------------

class WipProductReadSerializer(AuditReadMixin, serializers.ModelSerializer):
    binding   = RewoundCoreBindingReadSerializer(read_only=True)
    yard      = RewoundCoreYardReadSerializer(read_only=True)
    length_mm = RewoundCoreLengthMmReadSerializer(read_only=True)

    class Meta:
        model  = WipProduct
        fields = ["id", "name", "family", "binding", "yard", "length_mm",
                  "created_by", "updated_by", "created_at", "updated_at"]


class WipInventoryReadSerializer(serializers.ModelSerializer):
    product = WipProductReadSerializer(read_only=True)

    class Meta:
        model  = WipInventory
        fields = ["id", "product", "quantity", "last_updated_at"]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Recipe
# ---------------------------------------------------------------------------

class RecipeCreateSerializer(serializers.Serializer):
    name        = serializers.CharField(max_length=255)
    description = serializers.CharField()
    recipe_type = serializers.ChoiceField(choices=Recipe.RecipeType.choices, default=Recipe.RecipeType.REWINDING, required=False)


class RecipeMaterialConsumptionReadSerializer(serializers.ModelSerializer):
    purchase_item_id = serializers.IntegerField(source="purchase_item.id", read_only=True)
    product_name      = serializers.CharField(source="purchase_item.product.name", read_only=True)

    class Meta:
        model  = RecipeMaterialConsumption
        fields = ["id", "purchase_item_id", "product_name", "quantity", "unit_cost", "created_at"]
        read_only_fields = fields


class RecipeIssuedMaterialReadSerializer(serializers.ModelSerializer):
    product_id   = serializers.IntegerField(source="product.id", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)
    consumptions = RecipeMaterialConsumptionReadSerializer(many=True, read_only=True)

    class Meta:
        model  = RecipeIssuedMaterial
        fields = ["id", "kind", "product_id", "product_name", "product_code", "quantity", "consumptions"]
        read_only_fields = fields


class RecipeBreakdownItemReadSerializer(serializers.ModelSerializer):
    wip_product = WipProductReadSerializer(read_only=True)

    class Meta:
        model  = RecipeBreakdownItem
        fields = ["id", "wip_product", "quantity", "remaining_quantity", "unit_cost_snapshot", "created_at"]
        read_only_fields = fields


class RecipeReadSerializer(AuditReadMixin, serializers.ModelSerializer):
    issued_materials = RecipeIssuedMaterialReadSerializer(many=True, read_only=True)
    breakdown_items  = RecipeBreakdownItemReadSerializer(many=True, read_only=True)
    finished_by      = serializers.StringRelatedField(read_only=True)

    class Meta:
        model  = Recipe
        fields = [
            "id", "recipe_number", "recipe_type", "name", "description", "status",
            "cost_per_unit", "finished_by", "finished_at",
            "issued_materials", "breakdown_items",
            "created_by", "updated_by", "created_at", "updated_at",
        ]
        read_only_fields = fields


class IssueMaterialSerializer(serializers.Serializer):
    kind              = serializers.ChoiceField(choices=RecipeIssuedMaterial.MaterialKind.choices)
    product_id        = serializers.IntegerField()
    quantity          = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0.0001"))
    shelf_allocations = ShelfAllocationInputSerializer(many=True)


class UpdateIssuedMaterialSerializer(serializers.Serializer):
    quantity          = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0.0001"))
    shelf_allocations = ShelfAllocationInputSerializer(many=True)


class AddBreakdownItemSerializer(serializers.Serializer):
    yard_value        = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0.0001"))
    quantity          = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0.0001"))
    shelf_allocations = ShelfAllocationInputSerializer(many=True)


class IssuableProductSerializer(serializers.Serializer):
    id                 = serializers.IntegerField()
    name               = serializers.CharField()
    code               = serializers.CharField()
    available_quantity = serializers.DecimalField(max_digits=14, decimal_places=4, allow_null=True)


class CandidateShelfSerializer(serializers.Serializer):
    id                 = serializers.IntegerField()
    name               = serializers.CharField()
    available_quantity = serializers.DecimalField(max_digits=14, decimal_places=4, required=False, allow_null=True)
