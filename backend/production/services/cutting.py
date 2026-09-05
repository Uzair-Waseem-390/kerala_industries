from decimal import ROUND_HALF_UP, Decimal

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from purchases.services import _unique_constraint_guard, next_reference

from ..models import (
    CuttingBreakdownItem, CuttingBreakdownItemShelfAllocation, CuttingIssuedMaterial,
    CuttingMaterialConsumption, CuttingMaterialShelfDraw, Recipe, RecipeBreakdownItem,
    WipProduct, WipShelfStockMovement,
)
from ..selectors import get_available_wip_batches_for_fifo, get_cutting_issued_material
from ..utils import compute_wip_variant_key
from ..wip_inventory import apply_wip_shelf_allocations, sync_wip_inventory, validate_wip_shelf_consumption
from ._shared import (
    _fmt, draw_fifo, get_locked_recipe, normalize_shelf_allocations,
    require_under_processing, return_fifo,
)


def _next_cutting_recipe_number() -> str:
    return next_reference(counter_key="CUT", prefix_label="CUT", model=Recipe, field="recipe_number")


@transaction.atomic
def create_cutting_recipe(*, name: str, description: str = "", user) -> Recipe:
    """Thin wrapper — Cutting's own recipe_number sequence (CUT-2026-00xx), everything else identical to create_recipe."""
    from rest_framework.exceptions import ValidationError
    if not name or not name.strip():
        raise ValidationError({"name": "Name is required."})

    return Recipe.objects.create(
        recipe_number=_next_cutting_recipe_number(),
        recipe_type=Recipe.RecipeType.CUTTING,
        name=name.strip(),
        description=(description or "").strip(),
        created_by=user, updated_by=user,
    )


def _require_cutting_recipe(recipe: Recipe) -> None:
    from rest_framework.exceptions import ValidationError
    if recipe.recipe_type != Recipe.RecipeType.CUTTING:
        raise ValidationError({"recipe": "This is not a Cutting recipe."})


def _validate_core_is_issuable(product: WipProduct) -> None:
    from rest_framework.exceptions import ValidationError
    if product.stage != WipProduct.Stage.REWINDING:
        raise ValidationError({
            "wip_product_id": f"'{product.name}' is not a whole Rewound Core — it can't be issued into a Cutting recipe."
        })


def _core_unit_cost_fn(batch: RecipeBreakdownItem) -> Decimal:
    """
    A WIP batch's cost is already exact — frozen once at finish_recipe
    (Rewinding). No re-derivation needed (unlike RM batches, where unit_cost
    is total_price/quantity computed on the fly).
    """
    return batch.unit_cost_snapshot


@transaction.atomic
def issue_cutting_material(*, recipe_id: int, wip_product_id: int, quantity: Decimal, shelf_allocations: list[dict], user) -> CuttingIssuedMaterial:
    from rest_framework.exceptions import ValidationError

    recipe = get_locked_recipe(recipe_id)
    _require_cutting_recipe(recipe)
    require_under_processing(recipe)

    if quantity <= 0:
        raise ValidationError({"quantity": "Quantity must be greater than zero."})

    product = get_object_or_404(WipProduct, pk=wip_product_id, is_deleted=False)
    _validate_core_is_issuable(product)

    merged, shelves_by_id = normalize_shelf_allocations(shelf_allocations, required_total=quantity)
    validate_wip_shelf_consumption(product=product, allocations=[
        {"shelf": shelves_by_id[sid], "quantity": qty} for sid, qty in merged.items() if qty > 0
    ])

    with _unique_constraint_guard("Material has already been issued for this recipe."):
        issued = CuttingIssuedMaterial.objects.create(recipe=recipe, wip_product=product, quantity=quantity)

    batches = get_available_wip_batches_for_fifo(product.id, for_update=True)
    draw_fifo(
        issued_material=issued, quantity=quantity,
        consumption_model=CuttingMaterialConsumption, batch_field="wip_batch",
        batches=batches, unit_cost_fn=_core_unit_cost_fn,
        out_of_stock_label=product.name,
    )

    sync_wip_inventory(product=product, quantity_delta=-quantity, user=user)
    apply_wip_shelf_allocations(
        product=product,
        allocations=[{"shelf": shelves_by_id[sid], "quantity": qty} for sid, qty in merged.items() if qty > 0],
        sign=-1, reason=WipShelfStockMovement.Reason.CUTTING_ISSUE_CONSUMPTION,
        reference=recipe.recipe_number, user=user,
    )
    _record_cutting_shelf_draws(issued_material=issued, merged=merged, direction=CuttingMaterialShelfDraw.Direction.DRAW)
    return issued


def _record_cutting_shelf_draws(*, issued_material: CuttingIssuedMaterial, merged: dict, direction: str) -> None:
    if not merged:
        return
    CuttingMaterialShelfDraw.objects.bulk_create([
        CuttingMaterialShelfDraw(issued_material=issued_material, shelf_id=sid, direction=direction, quantity=qty)
        for sid, qty in merged.items() if qty > 0
    ])


@transaction.atomic
def update_cutting_issued_material(*, recipe_id: int, new_quantity: Decimal, shelf_allocations: list[dict], user) -> CuttingIssuedMaterial:
    """Increase (more FIFO draw, validated against available WIP stock) or decrease (FIFO return) — mirrors update_issued_material."""
    from rest_framework.exceptions import ValidationError

    recipe = get_locked_recipe(recipe_id)
    _require_cutting_recipe(recipe)
    require_under_processing(recipe)

    issued = get_object_or_404(
        CuttingIssuedMaterial.objects.select_for_update().select_related("wip_product"),
        recipe_id=recipe_id,
    )
    if new_quantity <= 0:
        raise ValidationError({"quantity": "Quantity must be greater than zero."})

    delta = new_quantity - issued.quantity
    if delta == 0:
        raise ValidationError({"quantity": "This is already the issued quantity."})

    product = issued.wip_product

    if delta > 0:
        merged, shelves_by_id = normalize_shelf_allocations(shelf_allocations, required_total=delta)
        validate_wip_shelf_consumption(product=product, allocations=[
            {"shelf": shelves_by_id[sid], "quantity": qty} for sid, qty in merged.items() if qty > 0
        ])
        batches = get_available_wip_batches_for_fifo(product.id, for_update=True)
        draw_fifo(
            issued_material=issued, quantity=delta,
            consumption_model=CuttingMaterialConsumption, batch_field="wip_batch",
            batches=batches, unit_cost_fn=_core_unit_cost_fn,
            out_of_stock_label=product.name,
        )
        sync_wip_inventory(product=product, quantity_delta=-delta, user=user)
        apply_wip_shelf_allocations(
            product=product,
            allocations=[{"shelf": shelves_by_id[sid], "quantity": qty} for sid, qty in merged.items() if qty > 0],
            sign=-1, reason=WipShelfStockMovement.Reason.CUTTING_ISSUE_CONSUMPTION,
            reference=recipe.recipe_number, user=user,
        )
        _record_cutting_shelf_draws(issued_material=issued, merged=merged, direction=CuttingMaterialShelfDraw.Direction.DRAW)
    else:
        give_back = abs(delta)
        merged, shelves_by_id = normalize_shelf_allocations(shelf_allocations, required_total=give_back)
        return_fifo(
            issued_material=issued, quantity=give_back,
            batch_model=RecipeBreakdownItem, batch_field="wip_batch",
            batch_lock_order_by=("recipe__finished_at", "pk"),
        )
        sync_wip_inventory(product=product, quantity_delta=give_back, user=user)
        apply_wip_shelf_allocations(
            product=product,
            allocations=[{"shelf": shelves_by_id[sid], "quantity": qty} for sid, qty in merged.items() if qty > 0],
            sign=1, reason=WipShelfStockMovement.Reason.CUTTING_ISSUE_CONSUMPTION,
            reference=recipe.recipe_number, user=user,
        )
        _record_cutting_shelf_draws(issued_material=issued, merged=merged, direction=CuttingMaterialShelfDraw.Direction.RETURN)

    issued.quantity = new_quantity
    issued.save(update_fields=["quantity"])
    return issued


@transaction.atomic
def add_cutting_breakdown_item(*, recipe_id: int, length_mm: Decimal, quantity: Decimal, shelf_allocations: list[dict], user) -> CuttingBreakdownItem:
    from django.http import Http404
    from rest_framework.exceptions import ValidationError

    recipe = get_locked_recipe(recipe_id)
    _require_cutting_recipe(recipe)
    require_under_processing(recipe)

    if length_mm <= 0:
        raise ValidationError({"length_mm": "Length (mm) must be greater than zero."})
    if quantity <= 0:
        raise ValidationError({"quantity": "Quantity must be greater than zero."})

    try:
        issued = get_cutting_issued_material(recipe_id=recipe_id)
    except Http404:
        raise ValidationError({"issued_material": "Cores must be issued before adding a breakdown item."})

    core_product = issued.wip_product
    if core_product.binding_id is None or core_product.yard_id is None:
        raise ValidationError({"issued_material": f"'{core_product.name}' is missing binding/yard attributes."})

    from ..models import RewoundCoreLengthMm
    length_lookup, _ = RewoundCoreLengthMm.objects.get_or_create(
        value=length_mm, defaults={"created_by": user, "updated_by": user},
    )

    variant_key = compute_wip_variant_key(
        binding_id=core_product.binding_id, yard_id=core_product.yard_id, length_mm_id=length_lookup.id,
        stage=WipProduct.Stage.CUTTING,
    )
    wip_product = WipProduct.objects.filter(variant_key=variant_key).first()
    if wip_product is None:
        name = f"{core_product.binding.value} {_fmt(core_product.yard.value)} yard {_fmt(length_lookup.value)}"
        try:
            with transaction.atomic():
                wip_product = WipProduct.objects.create(
                    name=name, family=core_product.family, binding=core_product.binding,
                    yard=core_product.yard, length_mm=length_lookup,
                    stage=WipProduct.Stage.CUTTING, variant_key=variant_key,
                    created_by=user, updated_by=user,
                )
        except IntegrityError:
            # Lost a create race against a concurrent identical breakdown —
            # OR the row occupying variant_key is soft-deleted, in which
            # case the pre-check above (soft-delete-filtered manager)
            # wouldn't have found it either. Mirrors
            # rewinding.add_breakdown_item's identical fix for the same race.
            wip_product = WipProduct.all_objects.filter(variant_key=variant_key).first()
            if wip_product is None:
                raise
            if wip_product.is_deleted:
                raise ValidationError({
                    "wip_product": (
                        f"A previously deleted WIP product ('{wip_product.name}') already used this "
                        f"exact attribute combination. Restore it before adding this breakdown item."
                    )
                })

    merged, shelves_by_id = normalize_shelf_allocations(shelf_allocations, required_total=quantity)

    item = CuttingBreakdownItem.objects.create(
        recipe=recipe, wip_product=wip_product, length_mm=length_mm,
        quantity=quantity, remaining_quantity=quantity,
        created_by=user, updated_by=user,
    )

    sync_wip_inventory(product=wip_product, quantity_delta=quantity, user=user)
    apply_wip_shelf_allocations(
        product=wip_product,
        allocations=[{"shelf": shelves_by_id[sid], "quantity": qty} for sid, qty in merged.items() if qty > 0],
        sign=1, reason=WipShelfStockMovement.Reason.CUTTING_BREAKDOWN_PUTAWAY,
        reference=recipe.recipe_number, user=user,
    )
    CuttingBreakdownItemShelfAllocation.objects.bulk_create([
        CuttingBreakdownItemShelfAllocation(breakdown_item=item, shelf_id=sid, quantity=qty)
        for sid, qty in merged.items() if qty > 0
    ])
    return item


@transaction.atomic
def finish_cutting_recipe(*, recipe_id: int, user) -> Recipe:
    """
    See instructions/architecture.md's waste-absorption rule for the full
    reasoning. Summary:
      1. total_cost = exact sum of what was paid for the issued cores (FIFO).
      2. total_issued_length_mm = issued core count × the core's own length_mm.
      3. breakdown_total_length_mm must not exceed that.
      4. waste_length_mm = the difference — reported, not silently dropped.
      5. cost_per_mm = total_cost / total_issued_length_mm.
      6. Each item's "before waste" cost = its own length × cost_per_mm
         (residual-to-last-item reconciled against breakdown_total_length_mm × cost_per_mm).
      7. waste_cost = total_cost − Σ(before-waste line costs); spread FLAT
         per produced piece (not by length) across every item, "final"
         cost = before-waste + flat waste share (residual-to-last-item
         reconciled so Σ(qty × final) == total_cost exactly).
    """
    from rest_framework.exceptions import ValidationError

    recipe = get_locked_recipe(recipe_id)
    _require_cutting_recipe(recipe)
    require_under_processing(recipe)

    if not recipe.description or not recipe.description.strip():
        raise ValidationError({"description": "Description is required before finishing this recipe."})

    breakdown_items = list(recipe.cutting_breakdown_items.all())
    if not breakdown_items:
        raise ValidationError({"breakdown_items": "At least one breakdown item is required to finish this recipe."})

    issued = get_cutting_issued_material(recipe_id=recipe_id)

    total_cost = Decimal("0")
    for consumption in issued.consumptions.all():
        total_cost += consumption.quantity * consumption.unit_cost

    total_issued_length_mm = issued.quantity * issued.wip_product.length_mm.value
    breakdown_total_length_mm = sum((item.quantity * item.length_mm for item in breakdown_items), Decimal("0"))

    if breakdown_total_length_mm > total_issued_length_mm:
        raise ValidationError({
            "breakdown_items": (
                f"Breakdown length ({breakdown_total_length_mm} mm) cannot exceed the "
                f"issued length ({total_issued_length_mm} mm)."
            )
        })

    waste_length_mm = total_issued_length_mm - breakdown_total_length_mm
    cost_per_mm = (total_cost / total_issued_length_mm) if total_issued_length_mm > 0 else Decimal("0")

    precision = Decimal("0.0001")

    # Step 1: "before waste" cost per item, length-weighted, residual on the last item.
    remaining_before_waste_cost = breakdown_total_length_mm * cost_per_mm
    for item in breakdown_items[:-1]:
        item.unit_cost_before_waste = (item.length_mm * cost_per_mm).quantize(precision, rounding=ROUND_HALF_UP)
        remaining_before_waste_cost -= item.quantity * item.unit_cost_before_waste
    last_item = breakdown_items[-1]
    last_item.unit_cost_before_waste = (
        (remaining_before_waste_cost / last_item.quantity).quantize(precision, rounding=ROUND_HALF_UP)
        if last_item.quantity > 0 else Decimal("0")
    )

    # Step 2: waste's cost is what's left of total_cost after the before-waste
    # allocation — spread FLAT per produced piece (not by length), residual
    # on the last item so Σ(qty × final) reconciles to total_cost exactly.
    total_output_pieces = sum((item.quantity for item in breakdown_items), Decimal("0"))
    before_waste_total_cost = sum((item.quantity * item.unit_cost_before_waste for item in breakdown_items), Decimal("0"))
    waste_cost = total_cost - before_waste_total_cost
    waste_per_piece = (waste_cost / total_output_pieces) if total_output_pieces > 0 else Decimal("0")

    remaining_total_cost = total_cost
    for item in breakdown_items[:-1]:
        item.unit_cost_snapshot = (item.unit_cost_before_waste + waste_per_piece).quantize(precision, rounding=ROUND_HALF_UP)
        remaining_total_cost -= item.quantity * item.unit_cost_snapshot
    last_item.unit_cost_snapshot = (
        (remaining_total_cost / last_item.quantity).quantize(precision, rounding=ROUND_HALF_UP)
        if last_item.quantity > 0 else Decimal("0")
    )

    CuttingBreakdownItem.objects.bulk_update(breakdown_items, ["unit_cost_before_waste", "unit_cost_snapshot"])

    recipe.status = Recipe.Status.FINISHED
    recipe.cost_per_unit = (total_cost / total_output_pieces).quantize(precision, rounding=ROUND_HALF_UP) if total_output_pieces > 0 else Decimal("0")
    recipe.waste_length_mm = waste_length_mm
    recipe.waste_cost = waste_cost.quantize(precision, rounding=ROUND_HALF_UP)
    recipe.finished_by = user
    recipe.finished_at = timezone.now()
    recipe.updated_by = user
    recipe.save(update_fields=[
        "status", "cost_per_unit", "waste_length_mm", "waste_cost",
        "finished_by", "finished_at", "updated_by", "updated_at",
    ])
    return recipe
