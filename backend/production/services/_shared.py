"""
Helpers shared by rewinding.py and cutting.py — recipe-locking, shelf
allocation shape-validation, decimal display formatting, and FIFO
draw/return. Kept here instead of duplicated per stage (see the 2026-09
discussion on not repeating purchases/billing's file-growth mistake).
"""
from decimal import Decimal

from purchases.services import _validate_shelf_ids_exist

from ..models import Recipe


def _fmt(value: Decimal) -> str:
    """'100.0000' -> '100', '1295.4000' -> '1295.4' — no trailing zeros/decimal point."""
    s = format(value, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def get_locked_recipe(recipe_id: int) -> Recipe:
    """
    Locks the Recipe row before any status check — every mutating service
    function must call this FIRST, inside its own @transaction.atomic. A
    plain unlocked read-then-check lets two concurrent requests both pass a
    status check before either commits its state change (e.g. two
    overlapping "Finish" clicks, or a finish racing an add-breakdown-item)
    — the row lock serializes them so the second request re-reads the true
    post-commit status.
    """
    from django.shortcuts import get_object_or_404
    return get_object_or_404(Recipe.objects.select_for_update(), pk=recipe_id, is_deleted=False)


def require_under_processing(recipe: Recipe) -> None:
    from rest_framework.exceptions import ValidationError
    if recipe.status != Recipe.Status.UNDER_PROCESSING:
        raise ValidationError({"status": "This recipe is finished and can no longer be edited."})


def normalize_shelf_allocations(allocations: list[dict], *, required_total: Decimal, field_label: str = "shelf_allocations"):
    """
    Shared shape-validation for every shelf-allocation input in this app:
    existence check, duplicate-merge, sum-must-equal-required. Returns
    (merged: {shelf_id: qty}, shelves_by_id).
    """
    from rest_framework.exceptions import ValidationError
    if not allocations:
        raise ValidationError({field_label: "At least one shelf allocation is required."})

    shelves_by_id = _validate_shelf_ids_exist([a["shelf_id"] for a in allocations])
    merged: dict[int, Decimal] = {}
    for a in allocations:
        merged[a["shelf_id"]] = merged.get(a["shelf_id"], Decimal("0")) + a["quantity"]

    total = sum(merged.values()) if merged else Decimal("0")
    if total != required_total:
        raise ValidationError({
            field_label: f"Shelf allocations must sum to exactly {required_total}, got {total}."
        })
    return merged, shelves_by_id


def draw_fifo(*, issued_material, quantity: Decimal, consumption_model, batch_field: str, batches, unit_cost_fn, out_of_stock_label: str) -> None:
    """
    Consumes `quantity` across `batches` (already select_for_update()'d and
    ordered oldest-first by the caller), oldest first. Creates one
    `consumption_model` row per batch drawn from (via `batch_field`) and
    decrements each batch's `remaining_quantity`. Raises if the batches
    don't have enough left combined.
    """
    from rest_framework.exceptions import ValidationError

    remaining_to_consume = quantity
    for batch in batches:
        if remaining_to_consume <= 0:
            break
        consume = min(batch.remaining_quantity, remaining_to_consume)
        unit_cost = unit_cost_fn(batch)

        consumption_model.objects.create(
            issued_material=issued_material, quantity=consume, unit_cost=unit_cost,
            **{batch_field: batch},
        )
        batch.remaining_quantity -= consume
        batch.save(update_fields=["remaining_quantity"])
        remaining_to_consume -= consume

    if remaining_to_consume > 0:
        raise ValidationError({
            "quantity": (
                f"Stock ran out mid-issue for '{out_of_stock_label}' — "
                f"{remaining_to_consume} short. Please refresh and try again."
            )
        })


def return_fifo(*, issued_material, quantity: Decimal, batch_model, batch_field: str, batch_lock_order_by: tuple) -> None:
    """
    Reverses `quantity` worth of this issued_material's consumption,
    most-recently-drawn batch first. Batches are located (by LIFO
    consumption order) WITHOUT locking first, then locked in ONE query
    ordered exactly the way draw_fifo locks them (oldest-first) before any
    row is mutated — see rewinding.py's original _return_fifo docstring for
    why (deadlock avoidance: a concurrent increase locks oldest-first via
    draw_fifo, so a concurrent decrease must lock in the same order, not
    LIFO, to avoid two requests locking the same two batches in opposite
    order).
    """
    from rest_framework.exceptions import ValidationError

    remaining_to_return = quantity
    candidates = []
    for consumption in issued_material.consumptions.order_by("-created_at", "-id"):
        if remaining_to_return <= 0:
            break
        give_back = min(consumption.quantity, remaining_to_return)
        candidates.append((consumption, give_back))
        remaining_to_return -= give_back

    if remaining_to_return > 0:
        raise ValidationError({"quantity": "Could not reconcile the returned quantity against consumption history."})

    batch_ids = {getattr(c, f"{batch_field}_id") for c, _ in candidates}
    locked_batches = {
        b.pk: b
        for b in batch_model.objects.select_for_update()
            .filter(pk__in=batch_ids).order_by(*batch_lock_order_by)
    }

    for consumption, give_back in candidates:
        locked_batch = locked_batches[getattr(consumption, f"{batch_field}_id")]
        locked_batch.remaining_quantity += give_back
        locked_batch.save(update_fields=["remaining_quantity"])

        if give_back == consumption.quantity:
            consumption.delete()
        else:
            consumption.quantity -= give_back
            consumption.save(update_fields=["quantity"])
