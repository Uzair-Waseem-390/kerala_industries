from decimal import Decimal

from rest_framework import serializers

from inventory.models import FgInventory, FgShelfStock, WipInventory, WipShelfStock
from purchases.serializers import ShelfAllocationInputSerializer

from .models import (
    CuttingBreakdownItem, CuttingBreakdownItemShelfAllocation, CuttingIssuedMaterial,
    CuttingMaterialConsumption, CuttingMaterialShelfDraw, FgProduct, PackingIssuedMaterial,
    PackingIssuedPiece, PackingMaterialConsumption, PackingMaterialShelfDraw, PackingOutputItem,
    PackingOutputShelfAllocation, PackingPieceConsumption, PackingPieceShelfDraw, Recipe,
    RecipeBreakdownItem, RecipeBreakdownItemShelfAllocation, RecipeIssuedMaterial, RecipeLabor,
    RecipeMachine, RecipeMaterialConsumption, RecipeMaterialShelfDraw, RewoundCoreBinding,
    RewoundCoreLengthMm, RewoundCoreYard, WipProduct,
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
        fields = ["id", "name", "code", "family", "stage", "binding", "yard", "length_mm",
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


# ---------------------------------------------------------------------------
# Recipe Labor / Machine — shared across all 3 recipe types (Recipe itself
# is one shared model). See production/services/_shared.py for the
# add/remove/set-time service functions and the DL+FOH pool calculation.
# ---------------------------------------------------------------------------

class RecipeLaborReadSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.name", read_only=True)

    class Meta:
        model  = RecipeLabor
        fields = ["id", "employee", "employee_name", "rate_per_hour_snapshot", "created_at"]
        read_only_fields = fields


class RecipeMachineReadSerializer(serializers.ModelSerializer):
    machine_name     = serializers.CharField(source="machine.name", read_only=True)
    machine_category = serializers.CharField(source="machine.category", read_only=True)

    class Meta:
        model  = RecipeMachine
        fields = ["id", "machine", "machine_name", "machine_category", "rate_per_hour_snapshot", "created_at"]
        read_only_fields = fields


class SetRecipeTimeSerializer(serializers.Serializer):
    time_hours   = serializers.IntegerField(min_value=0, default=0)
    time_minutes = serializers.IntegerField(min_value=0, max_value=59, default=0)


class AddRecipeLaborSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()


class AddRecipeMachineSerializer(serializers.Serializer):
    machine_id = serializers.IntegerField()


class RecipeBreakdownItemReadSerializer(serializers.ModelSerializer):
    wip_product       = WipProductReadSerializer(read_only=True)
    shelf_allocations = RecipeBreakdownItemShelfAllocationReadSerializer(many=True, read_only=True)

    class Meta:
        model  = RecipeBreakdownItem
        fields = ["id", "wip_product", "quantity", "remaining_quantity", "unit_cost_snapshot",
                  "full_unit_cost_snapshot", "shelf_allocations", "created_at"]
        read_only_fields = fields


class RecipeReadSerializer(AuditReadMixin, serializers.ModelSerializer):
    issued_materials = RecipeIssuedMaterialReadSerializer(many=True, read_only=True)
    breakdown_items  = RecipeBreakdownItemReadSerializer(many=True, read_only=True)
    labor_entries    = RecipeLaborReadSerializer(many=True, read_only=True)
    machine_entries  = RecipeMachineReadSerializer(many=True, read_only=True)
    finished_by      = serializers.StringRelatedField(read_only=True)

    class Meta:
        model  = Recipe
        fields = [
            "id", "recipe_number", "recipe_type", "name", "description", "status",
            "cost_per_unit", "full_cost_per_unit", "time_hours", "time_minutes",
            "finished_by", "finished_at",
            "issued_materials", "breakdown_items", "labor_entries", "machine_entries",
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
        # unit_cost_snapshot is labeled "After Waste" in the UI (unchanged
        # value — material cost only); full_unit_cost_snapshot adds this
        # recipe's DL+FOH share on top ("Full Cost").
        fields = ["id", "wip_product", "length_mm", "quantity", "remaining_quantity",
                  "unit_cost_before_waste", "unit_cost_snapshot", "full_unit_cost_snapshot",
                  "shelf_allocations", "created_at"]
        read_only_fields = fields


class CuttingRecipeReadSerializer(AuditReadMixin, serializers.ModelSerializer):
    cutting_issued_material  = CuttingIssuedMaterialReadSerializer(read_only=True)
    cutting_breakdown_items  = CuttingBreakdownItemReadSerializer(many=True, read_only=True)
    labor_entries            = RecipeLaborReadSerializer(many=True, read_only=True)
    machine_entries          = RecipeMachineReadSerializer(many=True, read_only=True)
    finished_by              = serializers.StringRelatedField(read_only=True)

    class Meta:
        model  = Recipe
        fields = [
            "id", "recipe_number", "recipe_type", "name", "description", "status",
            "cost_per_unit", "full_cost_per_unit", "time_hours", "time_minutes",
            "waste_length_mm", "waste_cost", "finished_by", "finished_at",
            "cutting_issued_material", "cutting_breakdown_items", "labor_entries", "machine_entries",
            "created_by", "updated_by", "created_at", "updated_at",
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# FG Product / Inventory - mirrors the WIP Product/Inventory section above,
# pointed at FgProduct/FgInventory/FgShelfStock instead.
# ---------------------------------------------------------------------------

class FgProductReadSerializer(AuditReadMixin, serializers.ModelSerializer):
    binding   = RewoundCoreBindingReadSerializer(read_only=True)
    yard      = RewoundCoreYardReadSerializer(read_only=True)
    length_mm = RewoundCoreLengthMmReadSerializer(read_only=True)

    class Meta:
        model  = FgProduct
        fields = ["id", "name", "code", "binding", "yard", "length_mm",
                  "created_by", "updated_by", "created_at", "updated_at"]


class FgInventoryReadSerializer(serializers.ModelSerializer):
    product = FgProductReadSerializer(read_only=True)

    class Meta:
        model  = FgInventory
        fields = ["id", "product", "quantity", "last_updated_at"]
        read_only_fields = fields


class FgProductLiteSerializer(serializers.ModelSerializer):
    """Minimal FG product shape for shelf-stock rows - mirrors WipProductLiteSerializer."""
    class Meta:
        model  = FgProduct
        fields = ["id", "name", "code"]


class FgShelfStockReadSerializer(serializers.ModelSerializer):
    """Powers the Shelf detail page's FG tab - mirrors WipShelfStockReadSerializer."""
    product = FgProductLiteSerializer(read_only=True)

    class Meta:
        model  = FgShelfStock
        fields = ["id", "product", "quantity", "last_updated_at"]
        read_only_fields = fields


class IssuableCuttingPieceSerializer(serializers.Serializer):
    """Cut Pieces (WIP, stage=cutting) issuable into a Packing recipe - mirrors IssuableWipCoreSerializer."""
    id                 = serializers.IntegerField()
    name               = serializers.CharField()
    available_quantity = serializers.DecimalField(max_digits=14, decimal_places=4, allow_null=True)


# ---------------------------------------------------------------------------
# Recipe (Packing) - separate read serializers from Rewinding/Cutting: the
# child models genuinely differ (two independent inputs - a Cut Piece and a
# Packing Material - no breakdown stage, a single output row instead of
# many). Same shared header fields either way.
# ---------------------------------------------------------------------------

class CreatePackingRecipeSerializer(serializers.Serializer):
    name        = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")


class IssuePackingPieceSerializer(serializers.Serializer):
    wip_product_id    = serializers.IntegerField()
    quantity          = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0.0001"))
    shelf_allocations = ShelfAllocationInputSerializer(many=True)


class IssuePackingMaterialSerializer(serializers.Serializer):
    product_id        = serializers.IntegerField()
    quantity          = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0.0001"))
    shelf_allocations = ShelfAllocationInputSerializer(many=True)


class FinishPackingRecipeSerializer(serializers.Serializer):
    """Packing has no breakdown step - the FG put-away shelves are chosen at finish time."""
    shelf_allocations = ShelfAllocationInputSerializer(many=True)


class PackingPieceShelfDrawReadSerializer(serializers.ModelSerializer):
    shelf_id   = serializers.IntegerField(source="shelf.id", read_only=True)
    shelf_name = serializers.CharField(source="shelf.name", read_only=True)

    class Meta:
        model  = PackingPieceShelfDraw
        fields = ["id", "shelf_id", "shelf_name", "direction", "quantity", "created_at"]
        read_only_fields = fields


class PackingPieceConsumptionReadSerializer(serializers.ModelSerializer):
    piece_batch_id       = serializers.IntegerField(source="piece_batch.id", read_only=True)
    product_name         = serializers.CharField(source="piece_batch.wip_product.name", read_only=True)
    source_recipe_number = serializers.CharField(source="piece_batch.recipe.recipe_number", read_only=True)

    class Meta:
        model  = PackingPieceConsumption
        fields = ["id", "piece_batch_id", "product_name", "source_recipe_number", "quantity", "unit_cost", "created_at"]
        read_only_fields = fields


class PackingIssuedPieceReadSerializer(serializers.ModelSerializer):
    wip_product  = WipProductReadSerializer(read_only=True)
    consumptions = PackingPieceConsumptionReadSerializer(many=True, read_only=True)
    shelf_draws  = PackingPieceShelfDrawReadSerializer(many=True, read_only=True)

    class Meta:
        model  = PackingIssuedPiece
        fields = ["id", "wip_product", "quantity", "consumptions", "shelf_draws"]
        read_only_fields = fields


class PackingMaterialShelfDrawReadSerializer(serializers.ModelSerializer):
    shelf_id   = serializers.IntegerField(source="shelf.id", read_only=True)
    shelf_name = serializers.CharField(source="shelf.name", read_only=True)

    class Meta:
        model  = PackingMaterialShelfDraw
        fields = ["id", "shelf_id", "shelf_name", "direction", "quantity", "created_at"]
        read_only_fields = fields


class PackingMaterialConsumptionReadSerializer(serializers.ModelSerializer):
    purchase_item_id = serializers.IntegerField(source="purchase_item.id", read_only=True)
    product_name      = serializers.CharField(source="purchase_item.product.name", read_only=True)

    class Meta:
        model  = PackingMaterialConsumption
        fields = ["id", "purchase_item_id", "product_name", "quantity", "unit_cost", "created_at"]
        read_only_fields = fields


class PackingIssuedMaterialReadSerializer(serializers.ModelSerializer):
    product_id   = serializers.IntegerField(source="product.id", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)
    consumptions = PackingMaterialConsumptionReadSerializer(many=True, read_only=True)
    shelf_draws  = PackingMaterialShelfDrawReadSerializer(many=True, read_only=True)

    class Meta:
        model  = PackingIssuedMaterial
        fields = ["id", "product_id", "product_name", "product_code", "quantity", "consumptions", "shelf_draws"]
        read_only_fields = fields


class PackingOutputShelfAllocationReadSerializer(serializers.ModelSerializer):
    shelf_id   = serializers.IntegerField(source="shelf.id", read_only=True)
    shelf_name = serializers.CharField(source="shelf.name", read_only=True)

    class Meta:
        model  = PackingOutputShelfAllocation
        fields = ["id", "shelf_id", "shelf_name", "quantity"]
        read_only_fields = fields


class PackingOutputItemReadSerializer(serializers.ModelSerializer):
    fg_product        = FgProductReadSerializer(read_only=True)
    shelf_allocations = PackingOutputShelfAllocationReadSerializer(many=True, read_only=True)

    class Meta:
        model  = PackingOutputItem
        # unit_cost_snapshot is labeled "Material Cost" in the UI (unchanged
        # value — piece cost + packing material cost); full_unit_cost_snapshot
        # adds this recipe's DL+FOH share on top ("Full Cost" — the FG
        # unit's full manufacturing cost, the basis for COGS at sale time).
        fields = ["id", "fg_product", "quantity", "remaining_quantity", "unit_cost_snapshot",
                  "full_unit_cost_snapshot", "shelf_allocations", "created_at"]
        read_only_fields = fields


class PackingRecipeReadSerializer(AuditReadMixin, serializers.ModelSerializer):
    packing_issued_piece    = PackingIssuedPieceReadSerializer(read_only=True)
    packing_issued_material = PackingIssuedMaterialReadSerializer(read_only=True)
    packing_output_item     = PackingOutputItemReadSerializer(read_only=True)
    labor_entries           = RecipeLaborReadSerializer(many=True, read_only=True)
    machine_entries         = RecipeMachineReadSerializer(many=True, read_only=True)
    finished_by             = serializers.StringRelatedField(read_only=True)

    class Meta:
        model  = Recipe
        fields = [
            "id", "recipe_number", "recipe_type", "name", "description", "status",
            "cost_per_unit", "full_cost_per_unit", "time_hours", "time_minutes",
            "finished_by", "finished_at",
            "packing_issued_piece", "packing_issued_material", "packing_output_item",
            "labor_entries", "machine_entries",
            "created_by", "updated_by", "created_at", "updated_at",
        ]
        read_only_fields = fields
