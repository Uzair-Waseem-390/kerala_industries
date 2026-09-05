from decimal import Decimal

from rest_framework import serializers

from inventory.models import WipInventory, WipShelfStock
from purchases.serializers import ShelfAllocationInputSerializer

from .models import (
    CuttingBreakdownItem, CuttingBreakdownItemShelfAllocation, CuttingIssuedMaterial,
    CuttingMaterialConsumption, CuttingMaterialShelfDraw, Recipe, RecipeBreakdownItem,
    RecipeBreakdownItemShelfAllocation, RecipeIssuedMaterial, RecipeMaterialConsumption,
    RecipeMaterialShelfDraw, RewoundCoreBinding, RewoundCoreLengthMm, RewoundCoreYard,
    WipProduct,
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
        fields = ["id", "name", "family", "stage", "binding", "yard", "length_mm",
                  "created_by", "updated_by", "created_at", "updated_at"]


class WipInventoryReadSerializer(serializers.ModelSerializer):
    product = WipProductReadSerializer(read_only=True)

    class Meta:
        model  = WipInventory
        fields = ["id", "product", "quantity", "last_updated_at"]
        read_only_fields = fields


class WipProductLiteSerializer(serializers.ModelSerializer):
    """Minimal WIP product shape for shelf-stock rows — mirrors purchases.ProductLiteSerializer."""
    class Meta:
        model  = WipProduct
        fields = ["id", "name", "stage"]


class WipShelfStockReadSerializer(serializers.ModelSerializer):
    """Powers the Shelf detail page's WIP tab — mirrors inventory.ShelfStockReadSerializer."""
    product = WipProductLiteSerializer(read_only=True)

    class Meta:
        model  = WipShelfStock
        fields = ["id", "product", "quantity", "last_updated_at"]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Recipe
# ---------------------------------------------------------------------------

class RecipeCreateSerializer(serializers.Serializer):
    name        = serializers.CharField(max_length=255)
    # Not required at creation — description becomes mandatory only at
    # finish time (see production.services.finish_recipe).
    description = serializers.CharField(required=False, allow_blank=True, default="")
    recipe_type = serializers.ChoiceField(choices=Recipe.RecipeType.choices, default=Recipe.RecipeType.REWINDING, required=False)


class UpdateRecipeDescriptionSerializer(serializers.Serializer):
    description = serializers.CharField(allow_blank=True)


class RecipeMaterialShelfDrawReadSerializer(serializers.ModelSerializer):
    shelf_id   = serializers.IntegerField(source="shelf.id", read_only=True)
    shelf_name = serializers.CharField(source="shelf.name", read_only=True)

    class Meta:
        model  = RecipeMaterialShelfDraw
        fields = ["id", "shelf_id", "shelf_name", "direction", "quantity", "created_at"]
        read_only_fields = fields


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
    shelf_draws  = RecipeMaterialShelfDrawReadSerializer(many=True, read_only=True)

    class Meta:
        model  = RecipeIssuedMaterial
        fields = ["id", "kind", "product_id", "product_name", "product_code", "quantity", "consumptions", "shelf_draws"]
        read_only_fields = fields


class RecipeBreakdownItemShelfAllocationReadSerializer(serializers.ModelSerializer):
    shelf_id   = serializers.IntegerField(source="shelf.id", read_only=True)
    shelf_name = serializers.CharField(source="shelf.name", read_only=True)

    class Meta:
        model  = RecipeBreakdownItemShelfAllocation
        fields = ["id", "shelf_id", "shelf_name", "quantity"]
        read_only_fields = fields


class RecipeBreakdownItemReadSerializer(serializers.ModelSerializer):
    wip_product       = WipProductReadSerializer(read_only=True)
    shelf_allocations = RecipeBreakdownItemShelfAllocationReadSerializer(many=True, read_only=True)

    class Meta:
        model  = RecipeBreakdownItem
        fields = ["id", "wip_product", "quantity", "remaining_quantity", "unit_cost_snapshot",
                  "shelf_allocations", "created_at"]
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


# ---------------------------------------------------------------------------
# Recipe (Cutting) — separate read serializers from Rewinding's: the child
# models genuinely differ (WIP-batch consumption instead of RM-batch,
# length_mm + two cost fields on the breakdown item, a single issued
# material instead of a Jumbo+Cores pair) so nesting them under the shared
# RecipeReadSerializer would either show empty Rewinding-shaped fields on a
# Cutting recipe or vice versa. Same shared header fields either way.
# ---------------------------------------------------------------------------

class CreateCuttingRecipeSerializer(serializers.Serializer):
    name        = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")


class IssueCuttingMaterialSerializer(serializers.Serializer):
    wip_product_id    = serializers.IntegerField()
    quantity          = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0.0001"))
    shelf_allocations = ShelfAllocationInputSerializer(many=True)


class AddCuttingBreakdownItemSerializer(serializers.Serializer):
    length_mm         = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0.0001"))
    quantity          = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0.0001"))
    shelf_allocations = ShelfAllocationInputSerializer(many=True)


class IssuableWipCoreSerializer(serializers.Serializer):
    id                 = serializers.IntegerField()
    name               = serializers.CharField()
    available_quantity = serializers.DecimalField(max_digits=14, decimal_places=4, allow_null=True)


class CuttingMaterialShelfDrawReadSerializer(serializers.ModelSerializer):
    shelf_id   = serializers.IntegerField(source="shelf.id", read_only=True)
    shelf_name = serializers.CharField(source="shelf.name", read_only=True)

    class Meta:
        model  = CuttingMaterialShelfDraw
        fields = ["id", "shelf_id", "shelf_name", "direction", "quantity", "created_at"]
        read_only_fields = fields


class CuttingMaterialConsumptionReadSerializer(serializers.ModelSerializer):
    wip_batch_id          = serializers.IntegerField(source="wip_batch.id", read_only=True)
    product_name          = serializers.CharField(source="wip_batch.wip_product.name", read_only=True)
    source_recipe_number  = serializers.CharField(source="wip_batch.recipe.recipe_number", read_only=True)

    class Meta:
        model  = CuttingMaterialConsumption
        fields = ["id", "wip_batch_id", "product_name", "source_recipe_number", "quantity", "unit_cost", "created_at"]
        read_only_fields = fields


class CuttingIssuedMaterialReadSerializer(serializers.ModelSerializer):
    wip_product_id   = serializers.IntegerField(source="wip_product.id", read_only=True)
    wip_product_name = serializers.CharField(source="wip_product.name", read_only=True)
    consumptions     = CuttingMaterialConsumptionReadSerializer(many=True, read_only=True)
    shelf_draws      = CuttingMaterialShelfDrawReadSerializer(many=True, read_only=True)

    class Meta:
        model  = CuttingIssuedMaterial
        fields = ["id", "wip_product_id", "wip_product_name", "quantity", "consumptions", "shelf_draws"]
        read_only_fields = fields


class CuttingBreakdownItemShelfAllocationReadSerializer(serializers.ModelSerializer):
    shelf_id   = serializers.IntegerField(source="shelf.id", read_only=True)
    shelf_name = serializers.CharField(source="shelf.name", read_only=True)

    class Meta:
        model  = CuttingBreakdownItemShelfAllocation
        fields = ["id", "shelf_id", "shelf_name", "quantity"]
        read_only_fields = fields


class CuttingBreakdownItemReadSerializer(serializers.ModelSerializer):
    wip_product       = WipProductReadSerializer(read_only=True)
    shelf_allocations = CuttingBreakdownItemShelfAllocationReadSerializer(many=True, read_only=True)

    class Meta:
        model  = CuttingBreakdownItem
        fields = ["id", "wip_product", "length_mm", "quantity", "remaining_quantity",
                  "unit_cost_before_waste", "unit_cost_snapshot", "shelf_allocations", "created_at"]
        read_only_fields = fields


class CuttingRecipeReadSerializer(AuditReadMixin, serializers.ModelSerializer):
    cutting_issued_material  = CuttingIssuedMaterialReadSerializer(read_only=True)
    cutting_breakdown_items  = CuttingBreakdownItemReadSerializer(many=True, read_only=True)
    finished_by              = serializers.StringRelatedField(read_only=True)

    class Meta:
        model  = Recipe
        fields = [
            "id", "recipe_number", "recipe_type", "name", "description", "status",
            "cost_per_unit", "waste_length_mm", "waste_cost", "finished_by", "finished_at",
            "cutting_issued_material", "cutting_breakdown_items",
            "created_by", "updated_by", "created_at", "updated_at",
        ]
        read_only_fields = fields
