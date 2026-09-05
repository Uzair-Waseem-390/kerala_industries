from decimal import ROUND_HALF_UP, Decimal

from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone

from inventory.models import FgShelfStockMovement, ProductRegistryEntry, ShelfStockMovement, WipShelfStockMovement
from inventory.services import (
    apply_fg_shelf_allocations, apply_shelf_allocations as apply_rm_shelf_allocations,
    apply_wip_shelf_allocations, create_registry_entry, sync_fg_inventory, sync_wip_inventory,
    validate_wip_shelf_consumption,
)
from inventory.services import sync_inventory as sync_rm_inventory
from purchases.models import PACKING_PRODUCT_CODE
from purchases.selectors import get_available_purchase_items_for_fifo, get_product_by_id
from purchases.services import _unique_constraint_guard, next_reference, validate_shelf_consumption

from ..models import (
    FgProduct, PackingIssuedMaterial, PackingIssuedPiece, PackingMaterialConsumption,
    PackingMaterialShelfDraw, PackingOutputItem, PackingOutputShelfAllocation,
    PackingPieceConsumption, PackingPieceShelfDraw, Recipe, WipProduct,
)
from ..selectors import get_available_cutting_batches_for_fifo, get_packing_issued_material, get_packing_issued_piece
from ..utils import compute_fg_variant_key
from ._shared import (
    _fmt, draw_fifo, get_locked_recipe, next_fg_product_code, normalize_shelf_allocations,
    require_under_processing, return_fifo,
)


def _next_packing_recipe_number() -> str:
    return next_reference(counter_key="PAK", prefix_label="PAK", model=Recipe, field="recipe_number")


@transaction.atomic
def create_packing_recipe(*, name: str, description: str = "", user) -> Recipe:
    """Thin wrapper — Packing's own recipe_number sequence (PAK-2026-00xx), everything else identical to create_recipe."""
    from rest_framework.exceptions import ValidationError
    if not name or not name.strip():
        raise ValidationError({"name": "Name is required."})

    return Recipe.objects.create(
        recipe_number=_next_packing_recipe_number(),
        recipe_type=Recipe.RecipeType.PACKING,
        name=name.strip(),
        description=(description or "").strip(),
        created_by=user, updated_by=user,
    )


def _require_packing_recipe(recipe: Recipe) -> None:
    from rest_framework.exceptions import ValidationError
    if recipe.recipe_type != Recipe.RecipeType.PACKING:
        raise ValidationError({"recipe": "This is not a Packing recipe."})


def _validate_piece_is_issuable(product: WipProduct) -> None:
    from rest_framework.exceptions import ValidationError
    if product.stage != WipProduct.Stage.CUTTING:
        raise ValidationError({
            "wip_product_id": f"'{product.name}' is not a Cut Piece — it can't be issued into a Packing recipe."
        })


def _validate_packing_material(product) -> None:
    from rest_framework.exceptions import ValidationError
    if product.base_product_id is None or product.base_product.code != PACKING_PRODUCT_CODE:
        raise ValidationError({"product_id": f"'{product.name}' is not a Packing Material variant."})


def _piece_unit_cost_fn(batch) -> Decimal:
    """A Cutting batch's cost is already exact — frozen once at finish_cutting_recipe. No re-derivation needed."""
    return batch.unit_cost_snapshot


def _packing_material_unit_cost_fn(batch) -> Decimal:
    return (
        (batch.total_price / batch.quantity).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        if batch.quantity > 0 else batch.unit_price
    )


# ---------------------------------------------------------------------------
# Issue / update piece (WIP, stage=cutting)
# ---------------------------------------------------------------------------

def _record_piece_shelf_draws(*, issued_piece: PackingIssuedPiece, merged: dict, direction: str) -> None:
    if not merged:
        return
    PackingPieceShelfDraw.objects.bulk_create([
        PackingPieceShelfDraw(issued_piece=issued_piece, shelf_id=sid, direction=direction, quantity=qty)
        for sid, qty in merged.items() if qty > 0
    ])


@transaction.atomic
def issue_packing_piece(*, recipe_id: int, wip_product_id: int, quantity: Decimal, shelf_allocations: list[dict], user) -> PackingIssuedPiece:
    from rest_framework.exceptions import ValidationError

    recipe = get_locked_recipe(recipe_id)
    _require_packing_recipe(recipe)
    require_under_processing(recipe)

    if quantity <= 0:
        raise ValidationError({"quantity": "Quantity must be greater than zero."})

    product = get_object_or_404(WipProduct, pk=wip_product_id, is_deleted=False)
    _validate_piece_is_issuable(product)

    merged, shelves_by_id = normalize_shelf_allocations(shelf_allocations, required_total=quantity)
    validate_wip_shelf_consumption(product=product, allocations=[
        {"shelf": shelves_by_id[sid], "quantity": qty} for sid, qty in merged.items() if qty > 0
    ])

    with _unique_constraint_guard("A piece has already been issued for this recipe."):
        issued = PackingIssuedPiece.objects.create(recipe=recipe, wip_product=product, quantity=quantity)

    batches = get_available_cutting_batches_for_fifo(product.id, for_update=True)
    draw_fifo(
        issued_material=issued, quantity=quantity,
        consumption_model=PackingPieceConsumption, batch_field="piece_batch",
        batches=batches, unit_cost_fn=_piece_unit_cost_fn,
        out_of_stock_label=product.name,
    )

    sync_wip_inventory(product=product, quantity_delta=-quantity, user=user)
    apply_wip_shelf_allocations(
        product=product,
        allocations=[{"shelf": shelves_by_id[sid], "quantity": qty} for sid, qty in merged.items() if qty > 0],
        sign=-1, reason=WipShelfStockMovement.Reason.PACKING_ISSUE_CONSUMPTION,
        reference=recipe.recipe_number, user=user,
    )
    _record_piece_shelf_draws(issued_piece=issued, merged=merged, direction=PackingPieceShelfDraw.Direction.DRAW)
    return issued


@transaction.atomic
def update_packing_issued_piece(*, recipe_id: int, new_quantity: Decimal, shelf_allocations: list[dict], user) -> PackingIssuedPiece:
    """Increase (more FIFO draw) or decrease (FIFO return) — mirrors update_cutting_issued_material."""
    from rest_framework.exceptions import ValidationError

    recipe = get_locked_recipe(recipe_id)
    _require_packing_recipe(recipe)
    require_under_processing(recipe)

    issued = get_object_or_404(
        PackingIssuedPiece.objects.select_for_update().select_related("wip_product"),
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
        batches = get_available_cutting_batches_for_fifo(product.id, for_update=True)
        draw_fifo(
            issued_material=issued, quantity=delta,
            consumption_model=PackingPieceConsumption, batch_field="piece_batch",
            batches=batches, unit_cost_fn=_piece_unit_cost_fn,
            out_of_stock_label=product.name,
        )
        sync_wip_inventory(product=product, quantity_delta=-delta, user=user)
        apply_wip_shelf_allocations(
            product=product,
            allocations=[{"shelf": shelves_by_id[sid], "quantity": qty} for sid, qty in merged.items() if qty > 0],
            sign=-1, reason=WipShelfStockMovement.Reason.PACKING_ISSUE_CONSUMPTION,
            reference=recipe.recipe_number, user=user,
        )
        _record_piece_shelf_draws(issued_piece=issued, merged=merged, direction=PackingPieceShelfDraw.Direction.DRAW)
    else:
        give_back = abs(delta)
        merged, shelves_by_id = normalize_shelf_allocations(shelf_allocations, required_total=give_back)
        from ..models import CuttingBreakdownItem
        return_fifo(
            issued_material=issued, quantity=give_back,
            batch_model=CuttingBreakdownItem, batch_field="piece_batch",
            batch_lock_order_by=("recipe__finished_at", "pk"),
        )
        sync_wip_inventory(product=product, quantity_delta=give_back, user=user)
        apply_wip_shelf_allocations(
            product=product,
            allocations=[{"shelf": shelves_by_id[sid], "quantity": qty} for sid, qty in merged.items() if qty > 0],
            sign=1, reason=WipShelfStockMovement.Reason.PACKING_ISSUE_CONSUMPTION,
            reference=recipe.recipe_number, user=user,
        )
        _record_piece_shelf_draws(issued_piece=issued, merged=merged, direction=PackingPieceShelfDraw.Direction.RETURN)

    issued.quantity = new_quantity
    issued.save(update_fields=["quantity"])
    return issued


# ---------------------------------------------------------------------------
# Issue / update packing material (RM, kg)
# ---------------------------------------------------------------------------

def _record_material_shelf_draws(*, issued_material: PackingIssuedMaterial, merged: dict, direction: str) -> None:
    if not merged:
        return
    PackingMaterialShelfDraw.objects.bulk_create([
        PackingMaterialShelfDraw(issued_material=issued_material, shelf_id=sid, direction=direction, quantity=qty)
        for sid, qty in merged.items() if qty > 0
    ])


def _draw_packing_material_fifo(*, issued_material: PackingIssuedMaterial, quantity: Decimal) -> None:
    batches = get_available_purchase_items_for_fifo(issued_material.product_id, for_update=True)
    draw_fifo(
        issued_material=issued_material, quantity=quantity,
        consumption_model=PackingMaterialConsumption, batch_field="purchase_item",
        batches=batches, unit_cost_fn=_packing_material_unit_cost_fn,
        out_of_stock_label=issued_material.product.name,
    )


@transaction.atomic
def issue_packing_material(*, recipe_id: int, product_id: int, quantity: Decimal, shelf_allocations: list[dict], user) -> PackingIssuedMaterial:
    from rest_framework.exceptions import ValidationError

    recipe = get_locked_recipe(recipe_id)
    _require_packing_recipe(recipe)
    require_under_processing(recipe)

    if quantity <= 0:
        raise ValidationError({"quantity": "Quantity must be greater than zero."})

    product = get_product_by_id(product_id)
    _validate_packing_material(product)

    merged, shelves_by_id = normalize_shelf_allocations(shelf_allocations, required_total=quantity)
    validate_shelf_consumption(product=product, allocations=[
        {"shelf": shelves_by_id[sid], "quantity": qty} for sid, qty in merged.items() if qty > 0
    ])

    with _unique_constraint_guard("Packing material has already been issued for this recipe."):
        issued = PackingIssuedMaterial.objects.create(recipe=recipe, product=product, quantity=quantity)

    _draw_packing_material_fifo(issued_material=issued, quantity=quantity)

    sync_rm_inventory(product=product, quantity_delta=-quantity, user=user)
    apply_rm_shelf_allocations(
        product=product,
        allocations=[{"shelf": shelves_by_id[sid], "quantity": qty} for sid, qty in merged.items() if qty > 0],
        sign=-1, reason=ShelfStockMovement.Reason.RECIPE_ISSUE_CONSUMPTION,
        reference=recipe.recipe_number, user=user,
    )
    _record_material_shelf_draws(issued_material=issued, merged=merged, direction=PackingMaterialShelfDraw.Direction.DRAW)
    return issued


@transaction.atomic
def update_packing_issued_material(*, recipe_id: int, new_quantity: Decimal, shelf_allocations: list[dict], user) -> PackingIssuedMaterial:
    """Increase (draws more from RM) or decrease (returns to RM) — mirrors update_issued_material."""
    from rest_framework.exceptions import ValidationError

    recipe = get_locked_recipe(recipe_id)
    _require_packing_recipe(recipe)
    require_under_processing(recipe)

    issued = get_object_or_404(
        PackingIssuedMaterial.objects.select_for_update().select_related("product"),
        recipe_id=recipe_id,
    )
    if new_quantity <= 0:
        raise ValidationError({"quantity": "Quantity must be greater than zero."})

    delta = new_quantity - issued.quantity
    if delta == 0:
        raise ValidationError({"quantity": "This is already the issued quantity."})

    product = issued.product

    if delta > 0:
        merged, shelves_by_id = normalize_shelf_allocations(shelf_allocations, required_total=delta)
        validate_shelf_consumption(product=product, allocations=[
            {"shelf": shelves_by_id[sid], "quantity": qty} for sid, qty in merged.items() if qty > 0
        ])
        _draw_packing_material_fifo(issued_material=issued, quantity=delta)
        sync_rm_inventory(product=product, quantity_delta=-delta, user=user)
        apply_rm_shelf_allocations(
            product=product,
            allocations=[{"shelf": shelves_by_id[sid], "quantity": qty} for sid, qty in merged.items() if qty > 0],
            sign=-1, reason=ShelfStockMovement.Reason.RECIPE_ISSUE_CONSUMPTION,
            reference=recipe.recipe_number, user=user,
        )
        _record_material_shelf_draws(issued_material=issued, merged=merged, direction=PackingMaterialShelfDraw.Direction.DRAW)
    else:
        give_back = abs(delta)
        merged, shelves_by_id = normalize_shelf_allocations(shelf_allocations, required_total=give_back)
        from purchases.models import PurchaseItem
        return_fifo(
            issued_material=issued, quantity=give_back,
            batch_model=PurchaseItem, batch_field="purchase_item",
            batch_lock_order_by=("order__confirmed_at", "pk"),
        )
        sync_rm_inventory(product=product, quantity_delta=give_back, user=user)
        apply_rm_shelf_allocations(
            product=product,
            allocations=[{"shelf": shelves_by_id[sid], "quantity": qty} for sid, qty in merged.items() if qty > 0],
            sign=1, reason=ShelfStockMovement.Reason.RECIPE_ISSUE_CONSUMPTION,
            reference=recipe.recipe_number, user=user,
        )
        _record_material_shelf_draws(issued_material=issued, merged=merged, direction=PackingMaterialShelfDraw.Direction.RETURN)

    issued.quantity = new_quantity
    issued.save(update_fields=["quantity"])
    return issued


# ---------------------------------------------------------------------------
# Finish — no breakdown stage. Output quantity == issued piece quantity,
# 1:1, no split. See instructions/architecture.md and the 2026-09 design
# discussion for why Packing doesn't need a waste-absorption step the way
# Cutting does (packing doesn't transform the product).
# ---------------------------------------------------------------------------

@transaction.atomic
def finish_packing_recipe(*, recipe_id: int, shelf_allocations: list[dict], user) -> Recipe:
    """
    Cost mechanism:
      1. piece_unit_cost = the issued piece's own already-locked FIFO cost
         (weighted average across whatever Cutting batches it drew from —
         each batch's unit_cost_snapshot was frozen at finish_cutting_recipe).
      2. total_packing_cost = exact sum of what was paid for the issued
         packing material (FIFO, same mechanism as every other RM issuance).
      3. packing_cost_per_piece = total_packing_cost / total_pieces_issued,
         spread flat (evenly) across every piece — not by length/weight,
         per the 2026-09 design discussion.
      4. fg_unit_cost = piece_unit_cost + packing_cost_per_piece.
      5. One FgProduct (get-or-create by the SAME identity as the source WIP
         piece — "no name change") receives quantity == issued piece
         quantity, 1:1, at fg_unit_cost.
    """
    from rest_framework.exceptions import ValidationError

    recipe = get_locked_recipe(recipe_id)
    _require_packing_recipe(recipe)
    require_under_processing(recipe)

    if not recipe.description or not recipe.description.strip():
        raise ValidationError({"description": "Description is required before finishing this recipe."})

    try:
        issued_piece = get_packing_issued_piece(recipe_id=recipe_id)
    except Http404:
        raise ValidationError({"issued_piece": "A piece must be issued before finishing this recipe."})
    try:
        issued_material = get_packing_issued_material(recipe_id=recipe_id)
    except Http404:
        raise ValidationError({"issued_material": "Packing material must be issued before finishing this recipe."})

    piece_product = issued_piece.wip_product
    total_pieces = issued_piece.quantity

    precision = Decimal("0.0001")

    # Combined into ONE total, divided ONCE — per architecture.md's "round
    # only at the final step" rule. Computing piece_unit_cost and
    # packing_cost_per_piece as two independently-quantized divisions and
    # summing them (the original approach here) double-rounds and can drift
    # from the true combined cost whenever total_pieces doesn't divide each
    # component evenly, even though it divides their sum evenly (or more
    # closely). With only one output row, this recipe's PackingOutputItem
    # IS "the last item" in the residual-to-last-item sense Cutting/Rewinding
    # use for their multi-row breakdowns — there's no second row to reconcile
    # against, so a single division against the combined total is the exact
    # analogue of that rule for a one-row output.
    total_cost = Decimal("0")
    for consumption in issued_material.consumptions.all():
        total_cost += consumption.quantity * consumption.unit_cost
    for consumption in issued_piece.consumptions.all():
        total_cost += consumption.quantity * consumption.unit_cost

    fg_unit_cost = (
        (total_cost / total_pieces).quantize(precision, rounding=ROUND_HALF_UP)
        if total_pieces > 0 else Decimal("0")
    )

    variant_key = compute_fg_variant_key(
        binding_id=piece_product.binding_id, yard_id=piece_product.yard_id, length_mm_id=piece_product.length_mm_id,
    )
    fg_product = FgProduct.objects.filter(variant_key=variant_key).first()
    if fg_product is None:
        try:
            with transaction.atomic():
                fg_product = FgProduct.objects.create(
                    name=piece_product.name, code=next_fg_product_code(),
                    binding=piece_product.binding, yard=piece_product.yard, length_mm=piece_product.length_mm,
                    variant_key=variant_key, created_by=user, updated_by=user,
                )
                create_registry_entry(
                    type=ProductRegistryEntry.Type.FINISHED_GOODS, fg_product=fg_product,
                    name=fg_product.name, code=fg_product.code, category="Finished Goods",
                )
        except IntegrityError:
            # Lost a create race against a concurrent identical Packing
            # finish — OR the row occupying variant_key is soft-deleted.
            # Mirrors add_cutting_breakdown_item's identical fix.
            fg_product = FgProduct.all_objects.filter(variant_key=variant_key).first()
            if fg_product is None:
                raise
            if fg_product.is_deleted:
                raise ValidationError({
                    "fg_product": (
                        f"A previously deleted FG product ('{fg_product.name}') already used this "
                        f"exact attribute combination. Restore it before finishing this recipe."
                    )
                })

    merged, shelves_by_id = normalize_shelf_allocations(shelf_allocations, required_total=total_pieces)

    output = PackingOutputItem.objects.create(
        recipe=recipe, fg_product=fg_product, quantity=total_pieces, remaining_quantity=total_pieces,
        unit_cost_snapshot=fg_unit_cost, created_by=user, updated_by=user,
    )

    sync_fg_inventory(product=fg_product, quantity_delta=total_pieces, user=user)
    apply_fg_shelf_allocations(
        product=fg_product,
        allocations=[{"shelf": shelves_by_id[sid], "quantity": qty} for sid, qty in merged.items() if qty > 0],
        sign=1, reason=FgShelfStockMovement.Reason.PACKING_OUTPUT_PUTAWAY,
        reference=recipe.recipe_number, user=user,
    )
    PackingOutputShelfAllocation.objects.bulk_create([
        PackingOutputShelfAllocation(output_item=output, shelf_id=sid, quantity=qty)
        for sid, qty in merged.items() if qty > 0
    ])

    recipe.status = Recipe.Status.FINISHED
    recipe.cost_per_unit = fg_unit_cost
    recipe.finished_by = user
    recipe.finished_at = timezone.now()
    recipe.updated_by = user
    recipe.save(update_fields=["status", "cost_per_unit", "finished_by", "finished_at", "updated_by", "updated_at"])
    return recipe
