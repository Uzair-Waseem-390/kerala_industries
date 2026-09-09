"""
Helpers shared by rewinding.py and cutting.py — recipe-locking, shelf
allocation shape-validation, decimal display formatting, and FIFO
draw/return. Kept here instead of duplicated per stage (see the 2026-09
discussion on not repeating purchases/billing's file-growth mistake).
"""
from decimal import ROUND_HALF_UP, Decimal

from purchases.services import _validate_shelf_ids_exist, next_reference

from ..models import Recipe, RecipeLabor, RecipeMachine


def next_wip_product_code() -> str:
    """Sequential code for a new WIP product: WIP-2026-0001. Same shared counter mechanism as recipe_number."""
    from ..models import WipProduct
    return next_reference(counter_key="WIP", prefix_label="WIP", model=WipProduct, field="code")


def next_fg_product_code() -> str:
    """Sequential code for a new FG product: FG-2026-0001."""
    from ..models import FgProduct
    return next_reference(counter_key="FG", prefix_label="FG", model=FgProduct, field="code")


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


# ---------------------------------------------------------------------------
# Manufacturing cost integration (Direct Labor / Factory Overhead) — shared
# across all three recipe types since Recipe itself is one shared model.
# See docs/cogs-gross-profit-engine-notes.md for the accounting reasoning:
# this computes the "Full Manufacturing Cost" (material + DL + FOH), which
# is NOT the same thing as COGS — COGS is only recognized when a unit is
# actually sold.
# ---------------------------------------------------------------------------

def validate_manufacturing_resources(*, category: str) -> None:
    """
    Called at recipe CREATION time (not finish). A recipe can't productively
    be started at all if there's no employee in the system, or no machine of
    the matching category — matches Recipe.RecipeType's own values
    (rewinding/cutting/packing) 1:1 against manufacturing_costs.Machine.category.
    """
    from rest_framework.exceptions import ValidationError
    from manufacturing_costs.models import Employee, Machine

    if not Employee.objects.filter(is_deleted=False).exists():
        raise ValidationError({
            "employee": "No employee has been added yet. Add at least one employee in Manufacturing Costs before starting a recipe."
        })
    if not Machine.objects.filter(category=category, is_deleted=False).exists():
        label = category.title()
        raise ValidationError({
            "machine": f"No {label} machine has been added. Add a {label} machine in Manufacturing Costs before starting this recipe."
        })


def validate_labor_and_machines(recipe: Recipe, *, labor: list = None, machines: list = None) -> None:
    """
    Called at FINISH time. Blocks finishing until time is entered and at
    least one employee + one machine are assigned — these three feed the
    DL+FOH pool calculation (compute_labor_overhead_pool below).

    Accepts already-materialized `labor`/`machines` lists so a caller that
    also needs compute_labor_overhead_pool right after doesn't pay for two
    separate queries per relation (.exists() here + .all() there) — pass
    get_recipe_labor_and_machines(recipe)'s result through both calls.
    """
    from rest_framework.exceptions import ValidationError

    if recipe.time_hours == 0 and recipe.time_minutes == 0:
        raise ValidationError({"time": "Time taken (hours/minutes) must be entered before finishing this recipe."})
    if labor is None:
        labor = list(recipe.labor_entries.all())
    if machines is None:
        machines = list(recipe.machine_entries.all())
    if not labor:
        raise ValidationError({"labor": "At least one employee must be assigned before finishing this recipe."})
    if not machines:
        raise ValidationError({"machines": "At least one machine must be assigned before finishing this recipe."})


def get_recipe_labor_and_machines(recipe: Recipe) -> tuple[list, list]:
    """One query per relation, reused by validate_labor_and_machines + compute_labor_overhead_pool."""
    return list(recipe.labor_entries.all()), list(recipe.machine_entries.all())


def set_recipe_time(*, recipe_id: int, hours: int, minutes: int, user) -> Recipe:
    from rest_framework.exceptions import ValidationError

    if hours < 0 or minutes < 0:
        raise ValidationError({"time": "Hours and minutes cannot be negative."})
    if minutes > 59:
        raise ValidationError({"time_minutes": "Minutes must be between 0 and 59."})

    recipe = get_locked_recipe(recipe_id)
    require_under_processing(recipe)
    recipe.time_hours = hours
    recipe.time_minutes = minutes
    recipe.updated_by = user
    recipe.save(update_fields=["time_hours", "time_minutes", "updated_by", "updated_at"])
    return recipe


def add_recipe_labor(*, recipe_id: int, employee_id: int, user) -> RecipeLabor:
    from django.db import IntegrityError, transaction
    from django.shortcuts import get_object_or_404
    from rest_framework.exceptions import ValidationError
    from manufacturing_costs.models import Employee

    recipe = get_locked_recipe(recipe_id)
    require_under_processing(recipe)
    employee = get_object_or_404(Employee.objects.filter(is_deleted=False), pk=employee_id)

    try:
        with transaction.atomic():
            return RecipeLabor.objects.create(
                recipe=recipe, employee=employee, rate_per_hour_snapshot=employee.rate_per_hour,
            )
    except IntegrityError:
        raise ValidationError({"employee_id": f"'{employee.name}' is already assigned to this recipe."})


def remove_recipe_labor(*, recipe_id: int, employee_id: int, user) -> None:
    recipe = get_locked_recipe(recipe_id)
    require_under_processing(recipe)
    RecipeLabor.objects.filter(recipe=recipe, employee_id=employee_id).delete()


def add_recipe_machine(*, recipe_id: int, machine_id: int, user) -> RecipeMachine:
    from django.db import IntegrityError, transaction
    from django.shortcuts import get_object_or_404
    from rest_framework.exceptions import ValidationError
    from manufacturing_costs.models import Machine

    recipe = get_locked_recipe(recipe_id)
    require_under_processing(recipe)
    machine = get_object_or_404(Machine.objects.filter(is_deleted=False), pk=machine_id)

    if machine.category != recipe.recipe_type:
        raise ValidationError({
            "machine_id": f"'{machine.name}' is a {machine.get_category_display()} machine — it can't be assigned to a {recipe.get_recipe_type_display()} recipe."
        })

    try:
        with transaction.atomic():
            return RecipeMachine.objects.create(
                recipe=recipe, machine=machine, rate_per_hour_snapshot=machine.rate_per_hour,
            )
    except IntegrityError:
        raise ValidationError({"machine_id": f"'{machine.name}' is already assigned to this recipe."})


def remove_recipe_machine(*, recipe_id: int, machine_id: int, user) -> None:
    recipe = get_locked_recipe(recipe_id)
    require_under_processing(recipe)
    RecipeMachine.objects.filter(recipe=recipe, machine_id=machine_id).delete()


def compute_labor_overhead_pool(recipe: Recipe, *, labor: list = None, machines: list = None) -> Decimal:
    """
    DL pool  = Σ(employee rate/hour) × total_hours
    FOH pool = Σ(machine rate/hour)  × total_hours
    total_hours = time_hours + time_minutes/60. Every selected employee and
    machine is assumed to have worked the recipe's full duration (per the
    2026-09 design — no per-employee/per-machine hours split).

    Accepts already-materialized `labor`/`machines` lists — see
    validate_labor_and_machines's docstring; callers should fetch once via
    get_recipe_labor_and_machines(recipe) and pass the same lists to both.
    """
    if labor is None:
        labor = list(recipe.labor_entries.all())
    if machines is None:
        machines = list(recipe.machine_entries.all())
    total_hours = Decimal(recipe.time_hours) + (Decimal(recipe.time_minutes) / Decimal(60))
    labor_rate_total = sum((e.rate_per_hour_snapshot for e in labor), Decimal("0"))
    machine_rate_total = sum((m.rate_per_hour_snapshot for m in machines), Decimal("0"))
    return (labor_rate_total + machine_rate_total) * total_hours


def spread_pool_flat(items: list, pool: Decimal, precision: Decimal = Decimal("0.0001")) -> dict:
    """
    Spreads `pool` flat (evenly per unit, not weighted) across `items`
    (each must have a `.quantity`), residual-on-last-item so
    Σ(item.quantity × share) == pool exactly — same pattern as
    finish_cutting_recipe's waste_cost spread. Returns {item: share}.
    """
    total_qty = sum((item.quantity for item in items), Decimal("0"))
    if total_qty <= 0:
        return {item: Decimal("0") for item in items}

    share = (pool / total_qty).quantize(precision, rounding=ROUND_HALF_UP)
    shares = {}
    remaining = pool
    for item in items[:-1]:
        shares[item] = share
        remaining -= item.quantity * share
    last_item = items[-1]
    shares[last_item] = (
        (remaining / last_item.quantity).quantize(precision, rounding=ROUND_HALF_UP)
        if last_item.quantity > 0 else Decimal("0")
    )
    return shares
