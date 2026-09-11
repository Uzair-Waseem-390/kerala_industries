"""
Opening WIP/FG stock (2026-09) — the WIP/FG twin of
purchases.services.create_opening_stock_order. Called by data_entry's thin
orchestration layer (data_entry.services), never anything data_entry owns
itself — data_entry gets deleted entirely after go-live, so every real row
this creates must live here, in production/inventory, forever.

Mirrors the RM precedent's shape exactly: RM opening stock is a real
PurchaseOrder (is_data_entry=True) under a fake "System" supplier, with real
PurchaseItem batches. This is a real Recipe (is_data_entry=True, see
production.models.Recipe) with real RecipeBreakdownItem/CuttingBreakdownItem/
PackingOutputItem batch rows underneath — a genuine, FIFO-consumable,
correctly-valued batch, just excluded from the normal Recipes list (see
production.selectors.rewinding.get_all_recipes) so it never looks like real
manufacturing work happened. Zero hours, no labor/machines attached, so
compute_labor_overhead_pool naturally returns 0 — nothing to accrue for
stock that was never actually produced here.
"""
from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from purchases.services import next_reference

from ..models import CuttingBreakdownItem, PackingOutputItem, Recipe, RecipeBreakdownItem, WipProduct
from ._shared import get_or_create_fg_product, get_or_create_wip_product


def _validate_items(items: list) -> None:
    if not items:
        raise ValidationError({"items": "At least one item is required."})
    for item in items:
        if not item.get("shelf_id"):
            raise ValidationError({"shelf_id": "A shelf is required for every opening stock item."})
        if not item.get("binding_id") or not item.get("yard_id") or not item.get("length_mm_id"):
            raise ValidationError({"items": "binding_id, yard_id, and length_mm_id are required for every item."})
        if Decimal(str(item["quantity"])) <= 0:
            raise ValidationError({"quantity": "Quantity must be greater than zero."})
        if Decimal(str(item["unit_cost"])) <= 0:
            raise ValidationError({"unit_cost": "Unit cost must be greater than zero."})


def _get_lookups(item: dict):
    from purchases.selectors import get_shelf_by_id

    from ..models import RewoundCoreBinding, RewoundCoreLengthMm, RewoundCoreYard

    binding = get_object_or_404_lookup(RewoundCoreBinding, item["binding_id"], "binding_id")
    yard = get_object_or_404_lookup(RewoundCoreYard, item["yard_id"], "yard_id")
    length_mm = get_object_or_404_lookup(RewoundCoreLengthMm, item["length_mm_id"], "length_mm_id")
    shelf = get_shelf_by_id(item["shelf_id"])
    return binding, yard, length_mm, shelf


def get_object_or_404_lookup(model, pk, field_label):
    from django.shortcuts import get_object_or_404
    try:
        return get_object_or_404(model, pk=pk, is_deleted=False)
    except Exception:
        raise ValidationError({field_label: f"No such {model.__name__} (id={pk})."})


def create_opening_wip_stock(*, items: list, user) -> Recipe:
    """
    items: [{"binding_id", "yard_id", "length_mm_id", "stage" ("rewinding"=
    core or "cutting"=piece), "quantity", "unit_cost", "shelf_id"}, ...]
    One shared "Opening Stock" Recipe per call, one batch row per item.
    """
    from inventory.models import WipShelfStockMovement
    from inventory.services import apply_wip_shelf_allocations, sync_wip_inventory

    _validate_items(items)
    for item in items:
        if item.get("stage") not in (WipProduct.Stage.REWINDING, WipProduct.Stage.CUTTING):
            raise ValidationError({"stage": "stage must be 'rewinding' (core) or 'cutting' (piece)."})

    with transaction.atomic():
        recipe = Recipe.objects.create(
            recipe_number=next_reference(counter_key="REC", prefix_label="REC", model=Recipe, field="recipe_number"),
            recipe_type=Recipe.RecipeType.REWINDING,
            name="Opening Stock (Data Entry)",
            status=Recipe.Status.FINISHED,
            is_data_entry=True,
            created_by=user, updated_by=user,
        )
        for item in items:
            binding, yard, length_mm, shelf = _get_lookups(item)
            quantity = Decimal(str(item["quantity"]))
            unit_cost = Decimal(str(item["unit_cost"]))
            stage = item["stage"]

            wip_product = get_or_create_wip_product(
                binding=binding, yard=yard, length_mm=length_mm, stage=stage, user=user,
            )

            if stage == WipProduct.Stage.REWINDING:
                RecipeBreakdownItem.objects.create(
                    recipe=recipe, wip_product=wip_product, quantity=quantity, remaining_quantity=quantity,
                    unit_cost_snapshot=unit_cost, full_unit_cost_snapshot=unit_cost,
                    created_by=user, updated_by=user,
                )
                reason = WipShelfStockMovement.Reason.RECIPE_BREAKDOWN_PUTAWAY
            else:
                CuttingBreakdownItem.objects.create(
                    recipe=recipe, wip_product=wip_product, length_mm=length_mm.value,
                    quantity=quantity, remaining_quantity=quantity,
                    unit_cost_before_waste=unit_cost, unit_cost_snapshot=unit_cost,
                    full_unit_cost_snapshot=unit_cost,
                    created_by=user, updated_by=user,
                )
                reason = WipShelfStockMovement.Reason.CUTTING_BREAKDOWN_PUTAWAY

            sync_wip_inventory(product=wip_product, quantity_delta=quantity, user=user)
            apply_wip_shelf_allocations(
                product=wip_product, allocations=[{"shelf": shelf, "quantity": quantity}],
                sign=1, reason=reason, reference=recipe.recipe_number, user=user,
            )

    return recipe


def create_opening_fg_stock(*, items: list, user) -> list[Recipe]:
    """
    items: [{"binding_id", "yard_id", "length_mm_id", "quantity", "unit_cost", "shelf_id"}, ...]

    Unlike WIP (RecipeBreakdownItem/CuttingBreakdownItem, plain ForeignKeys
    to Recipe — several items can share one recipe), PackingOutputItem.recipe
    is a OneToOneField: exactly one packing output per recipe, matching how
    a real packing recipe always produces exactly one output row. So this
    creates one "Opening Stock" Recipe PER ITEM, not one shared recipe for
    the whole call — returns the list of recipes created.
    """
    from inventory.models import FgShelfStockMovement
    from inventory.services import apply_fg_shelf_allocations, sync_fg_inventory

    _validate_items(items)

    recipes = []
    with transaction.atomic():
        for item in items:
            binding, yard, length_mm, shelf = _get_lookups(item)
            quantity = Decimal(str(item["quantity"]))
            unit_cost = Decimal(str(item["unit_cost"]))

            recipe = Recipe.objects.create(
                recipe_number=next_reference(counter_key="REC", prefix_label="REC", model=Recipe, field="recipe_number"),
                recipe_type=Recipe.RecipeType.PACKING,
                name="Opening Stock (Data Entry)",
                status=Recipe.Status.FINISHED,
                is_data_entry=True,
                created_by=user, updated_by=user,
            )
            recipes.append(recipe)

            fg_product = get_or_create_fg_product(binding=binding, yard=yard, length_mm=length_mm, user=user)

            PackingOutputItem.objects.create(
                recipe=recipe, fg_product=fg_product, quantity=quantity, remaining_quantity=quantity,
                unit_cost_snapshot=unit_cost, full_unit_cost_snapshot=unit_cost,
                created_by=user, updated_by=user,
            )
            sync_fg_inventory(product=fg_product, quantity_delta=quantity, user=user)
            apply_fg_shelf_allocations(
                product=fg_product, allocations=[{"shelf": shelf, "quantity": quantity}],
                sign=1, reason=FgShelfStockMovement.Reason.PACKING_OUTPUT_PUTAWAY,
                reference=recipe.recipe_number, user=user,
            )

    return recipes
