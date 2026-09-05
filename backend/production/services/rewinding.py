from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from inventory.models import ShelfStockMovement
from inventory.services import apply_shelf_allocations as apply_rm_shelf_allocations
from inventory.services import sync_inventory as sync_rm_inventory
from purchases.models import CORES_PRODUCT_CODE, Family, JUMBO_PRODUCT_CODE
from purchases.selectors import get_available_purchase_items_for_fifo, get_product_by_id
from purchases.services import (
    _unique_constraint_guard, next_reference,
    validate_allocations_complete, validate_shelf_consumption,
)

from ..models import (
    Recipe, RecipeBreakdownItem, RecipeBreakdownItemShelfAllocation, RecipeIssuedMaterial,
    RecipeMaterialConsumption, RecipeMaterialShelfDraw, RewoundCoreBinding, RewoundCoreLengthMm,
    RewoundCoreYard, WipProduct, WipShelfStockMovement,
)
from ..selectors import get_issued_material
from ..utils import compute_wip_variant_key, inches_to_mm
from ..wip_inventory import apply_wip_shelf_allocations, sync_wip_inventory
from ._shared import (
    _fmt, draw_fifo, get_locked_recipe, normalize_shelf_allocations,
    require_under_processing, return_fifo,
)


def _next_recipe_number() -> str:
    return next_reference(counter_key="REC", prefix_label="REC", model=Recipe, field="recipe_number")


def _parse_decimal(value: str, *, field_label: str) -> Decimal:
    """
    RM attribute lookup values (e.g. CoreLength.value) are free-text
    CharFields — parses a numeric value out of one, tolerating a unit
    suffix like "51 inches". Raises a clear ValidationError if nothing
    numeric can be extracted, instead of silently guessing.
    """
    from rest_framework.exceptions import ValidationError
    raw = str(value).strip()
    try:
        return Decimal(raw)
    except InvalidOperation:
        pass
    numeric = "".join(ch for ch in raw if ch.isdigit() or ch == ".")
    try:
        if numeric:
            return Decimal(numeric)
    except InvalidOperation:
        pass
    raise ValidationError({
        field_label: f"'{value}' is not a numeric value and can't be converted."
    })


# ---------------------------------------------------------------------------
# Recipe header
# ---------------------------------------------------------------------------

@transaction.atomic
def create_recipe(*, name: str, description: str = "", recipe_type: str = Recipe.RecipeType.REWINDING, user) -> Recipe:
    """
    description is NOT required here — it's required before finish_recipe
    instead (see finish_recipe), so the user can fill it in any time while
    the recipe is under_processing.
    """
    from rest_framework.exceptions import ValidationError
    if not name or not name.strip():
        raise ValidationError({"name": "Name is required."})

    return Recipe.objects.create(
        recipe_number=_next_recipe_number(),
        recipe_type=recipe_type,
        name=name.strip(),
        description=(description or "").strip(),
        created_by=user, updated_by=user,
    )


@transaction.atomic
def update_recipe_description(*, recipe_id: int, description: str, user) -> Recipe:
    recipe = _get_locked_recipe(recipe_id)
    _require_under_processing(recipe)
    recipe.description = (description or "").strip()
    recipe.updated_by = user
    recipe.save(update_fields=["description", "updated_by", "updated_at"])
    return recipe


# Local aliases — these three are now generic, shared with cutting.py (see
# services/_shared.py); kept under their original names here so every
# existing call site in this file needs no change.
_get_locked_recipe = get_locked_recipe
_require_under_processing = require_under_processing
_normalize_shelf_allocations = normalize_shelf_allocations


def _validate_material_kind_matches_product(*, kind: str, product) -> None:
    from rest_framework.exceptions import ValidationError
    expected_code = JUMBO_PRODUCT_CODE if kind == RecipeIssuedMaterial.MaterialKind.JUMBO else CORES_PRODUCT_CODE
    if product.base_product_id is None or product.base_product.code != expected_code:
        raise ValidationError({
            "product_id": f"'{product.name}' is not a {kind} variant with attributes selected."
        })


def _draw_fifo(*, issued_material: RecipeIssuedMaterial, quantity: Decimal, user) -> None:
    """
    Consumes `quantity` of issued_material.product from RM purchase batches,
    oldest first — same mechanism as billing._run_fifo. Thin wrapper over
    the FIFO logic shared with Cutting (see services/_shared.py) — this
    function only supplies what's Rewinding/RM-specific: which batches, how
    to price one, and the out-of-stock label.
    """
    batches = get_available_purchase_items_for_fifo(issued_material.product_id, for_update=True)

    def unit_cost_fn(batch):
        return (
            (batch.total_price / batch.quantity).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            if batch.quantity > 0 else batch.unit_price
        )

    draw_fifo(
        issued_material=issued_material, quantity=quantity,
        consumption_model=RecipeMaterialConsumption, batch_field="purchase_item",
        batches=batches, unit_cost_fn=unit_cost_fn,
        out_of_stock_label=issued_material.product.name,
    )


def _return_fifo(*, issued_material: RecipeIssuedMaterial, quantity: Decimal) -> None:
    """
    Reverses `quantity` worth of this issued_material's consumption,
    most-recently-drawn batch first — the inverse of _draw_fifo. Thin
    wrapper over the shared FIFO-return logic (see services/_shared.py);
    locks batches oldest-confirmed-first (same order _draw_fifo locks them)
    to avoid a circular-wait deadlock against a concurrent increase.
    """
    from purchases.models import PurchaseItem

    return_fifo(
        issued_material=issued_material, quantity=quantity,
        batch_model=PurchaseItem, batch_field="purchase_item",
        batch_lock_order_by=("order__confirmed_at", "pk"),
    )


# ---------------------------------------------------------------------------
# Issue / update RM material
# ---------------------------------------------------------------------------

def _record_shelf_draws(*, issued_material: RecipeIssuedMaterial, merged: dict, direction: str) -> None:
    """
    Audit-only record of which shelf(s) an issue/increase drew from, or a
    decrease returned to — powers the "Drawn From" display on the recipe
    detail page. One bulk_create, same cost class as the consumptions
    already recorded in the same transaction — no extra round trips added
    to any list endpoint (only ever read via the recipe detail page's
    existing per-issued-material prefetch).
    """
    if not merged:
        return
    RecipeMaterialShelfDraw.objects.bulk_create([
        RecipeMaterialShelfDraw(issued_material=issued_material, shelf_id=sid, direction=direction, quantity=qty)
        for sid, qty in merged.items() if qty > 0
    ])


@transaction.atomic
def issue_material(*, recipe_id: int, kind: str, product_id: int, quantity: Decimal, shelf_allocations: list[dict], user) -> RecipeIssuedMaterial:
    from rest_framework.exceptions import ValidationError

    recipe = _get_locked_recipe(recipe_id)
    _require_under_processing(recipe)

    if quantity <= 0:
        raise ValidationError({"quantity": "Quantity must be greater than zero."})

    product = get_product_by_id(product_id)
    _validate_material_kind_matches_product(kind=kind, product=product)

    merged, shelves_by_id = _normalize_shelf_allocations(shelf_allocations, required_total=quantity)
    validate_shelf_consumption(product=product, allocations=[
        {"shelf": shelves_by_id[sid], "quantity": qty} for sid, qty in merged.items() if qty > 0
    ])

    with _unique_constraint_guard(f"A {kind} material has already been issued for this recipe."):
        issued = RecipeIssuedMaterial.objects.create(recipe=recipe, kind=kind, product=product, quantity=quantity)

    _draw_fifo(issued_material=issued, quantity=quantity, user=user)

    sync_rm_inventory(product=product, quantity_delta=-quantity, user=user)
    apply_rm_shelf_allocations(
        product=product,
        allocations=[{"shelf": shelves_by_id[sid], "quantity": qty} for sid, qty in merged.items() if qty > 0],
        sign=-1, reason=ShelfStockMovement.Reason.RECIPE_ISSUE_CONSUMPTION,
        reference=recipe.recipe_number, user=user,
    )
    _record_shelf_draws(issued_material=issued, merged=merged, direction=RecipeMaterialShelfDraw.Direction.DRAW)
    return issued


@transaction.atomic
def update_issued_material(*, recipe_id: int, kind: str, new_quantity: Decimal, shelf_allocations: list[dict], user) -> RecipeIssuedMaterial:
    """
    Increase (draws more from RM, same validation as issue_material) or
    decrease (returns the difference to RM — no separate return endpoint).
    shelf_allocations means "pull from" on increase, "return to" on decrease.
    """
    from rest_framework.exceptions import ValidationError

    recipe = _get_locked_recipe(recipe_id)
    _require_under_processing(recipe)

    # Locked BEFORE reading .quantity — two concurrent PATCHes on the same
    # (recipe, kind) row must not both compute their delta from the same
    # stale quantity (a lost-update race: the second save would silently
    # overwrite the first's change instead of building on it).
    issued = get_object_or_404(RecipeIssuedMaterial.objects.select_for_update().select_related("product"), recipe_id=recipe_id, kind=kind)
    if new_quantity <= 0:
        raise ValidationError({"quantity": "Quantity must be greater than zero."})

    delta = new_quantity - issued.quantity
    if delta == 0:
        raise ValidationError({"quantity": "This is already the issued quantity."})

    product = issued.product

    if delta > 0:
        merged, shelves_by_id = _normalize_shelf_allocations(shelf_allocations, required_total=delta)
        validate_shelf_consumption(product=product, allocations=[
            {"shelf": shelves_by_id[sid], "quantity": qty} for sid, qty in merged.items() if qty > 0
        ])
        _draw_fifo(issued_material=issued, quantity=delta, user=user)
        sync_rm_inventory(product=product, quantity_delta=-delta, user=user)
        apply_rm_shelf_allocations(
            product=product,
            allocations=[{"shelf": shelves_by_id[sid], "quantity": qty} for sid, qty in merged.items() if qty > 0],
            sign=-1, reason=ShelfStockMovement.Reason.RECIPE_ISSUE_CONSUMPTION,
            reference=recipe.recipe_number, user=user,
        )
        _record_shelf_draws(issued_material=issued, merged=merged, direction=RecipeMaterialShelfDraw.Direction.DRAW)
    else:
        give_back = abs(delta)
        merged, shelves_by_id = _normalize_shelf_allocations(shelf_allocations, required_total=give_back)
        _return_fifo(issued_material=issued, quantity=give_back)
        sync_rm_inventory(product=product, quantity_delta=give_back, user=user)
        apply_rm_shelf_allocations(
            product=product,
            allocations=[{"shelf": shelves_by_id[sid], "quantity": qty} for sid, qty in merged.items() if qty > 0],
            sign=1, reason=ShelfStockMovement.Reason.RECIPE_ISSUE_CONSUMPTION,
            reference=recipe.recipe_number, user=user,
        )
        _record_shelf_draws(issued_material=issued, merged=merged, direction=RecipeMaterialShelfDraw.Direction.RETURN)

    issued.quantity = new_quantity
    issued.save(update_fields=["quantity"])
    return issued


# ---------------------------------------------------------------------------
# Breakdown (output)
# ---------------------------------------------------------------------------

@transaction.atomic
def add_breakdown_item(*, recipe_id: int, yard_value: Decimal, quantity: Decimal, shelf_allocations: list[dict], user) -> RecipeBreakdownItem:
    from rest_framework.exceptions import ValidationError

    recipe = _get_locked_recipe(recipe_id)
    _require_under_processing(recipe)

    if yard_value <= 0:
        raise ValidationError({"yard_value": "Yard value must be greater than zero."})
    if quantity <= 0:
        raise ValidationError({"quantity": "Quantity must be greater than zero."})

    from django.http import Http404
    try:
        jumbo_material = get_issued_material(recipe_id=recipe_id, kind=RecipeIssuedMaterial.MaterialKind.JUMBO)
        cores_material = get_issued_material(recipe_id=recipe_id, kind=RecipeIssuedMaterial.MaterialKind.CORES)
    except Http404:
        raise ValidationError({"issued_materials": "Both Jumbo and Cores must be issued before adding a breakdown item."})

    jumbo_product = jumbo_material.product
    cores_product = cores_material.product
    if jumbo_product.jumbo_name_id is None:
        raise ValidationError({"issued_materials": f"'{jumbo_product.name}' has no Jumbo Name attribute set."})
    if cores_product.core_length_id is None:
        raise ValidationError({"issued_materials": f"'{cores_product.name}' has no Core Length attribute set."})

    binding_value = jumbo_product.jumbo_name.value
    length_inches = _parse_decimal(cores_product.core_length.value, field_label="core_length")
    length_mm_value = inches_to_mm(length_inches)

    with transaction.atomic():
        binding, _ = RewoundCoreBinding.objects.get_or_create(
            value=binding_value, defaults={"created_by": user, "updated_by": user},
        )
        yard_lookup, _ = RewoundCoreYard.objects.get_or_create(
            value=yard_value, defaults={"created_by": user, "updated_by": user},
        )
        length_lookup, _ = RewoundCoreLengthMm.objects.get_or_create(
            value=length_mm_value, defaults={"created_by": user, "updated_by": user},
        )

    variant_key = compute_wip_variant_key(
        binding_id=binding.id, yard_id=yard_lookup.id, length_mm_id=length_lookup.id,
        stage=WipProduct.Stage.REWINDING,
    )
    wip_product = WipProduct.objects.filter(variant_key=variant_key).first()
    if wip_product is None:
        wip_family = Family.objects.get(name="WIP")
        name = f"{binding.value} {_fmt(yard_lookup.value)} yard {_fmt(length_lookup.value)}"
        try:
            with transaction.atomic():
                wip_product = WipProduct.objects.create(
                    name=name, family=wip_family, binding=binding, yard=yard_lookup, length_mm=length_lookup,
                    stage=WipProduct.Stage.REWINDING, variant_key=variant_key, created_by=user, updated_by=user,
                )
        except IntegrityError:
            # Lost a create race against a concurrent identical breakdown —
            # OR the row occupying variant_key is soft-deleted, in which
            # case the pre-check above (soft-delete-filtered manager)
            # wouldn't have found it either. Mirrors
            # purchases.services.get_or_create_product_variant's identical
            # fix for the same race.
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

    merged, shelves_by_id = _normalize_shelf_allocations(shelf_allocations, required_total=quantity)

    item = RecipeBreakdownItem.objects.create(
        recipe=recipe, wip_product=wip_product, quantity=quantity, remaining_quantity=quantity,
        created_by=user, updated_by=user,
    )

    sync_wip_inventory(product=wip_product, quantity_delta=quantity, user=user)
    apply_wip_shelf_allocations(
        product=wip_product,
        allocations=[{"shelf": shelves_by_id[sid], "quantity": qty} for sid, qty in merged.items() if qty > 0],
        sign=1, reason=WipShelfStockMovement.Reason.RECIPE_BREAKDOWN_PUTAWAY,
        reference=recipe.recipe_number, user=user,
    )
    RecipeBreakdownItemShelfAllocation.objects.bulk_create([
        RecipeBreakdownItemShelfAllocation(breakdown_item=item, shelf_id=sid, quantity=qty)
        for sid, qty in merged.items() if qty > 0
    ])
    return item


@transaction.atomic
def finish_recipe(*, recipe_id: int, user) -> Recipe:
    from rest_framework.exceptions import ValidationError

    recipe = _get_locked_recipe(recipe_id)
    _require_under_processing(recipe)

    if not recipe.description or not recipe.description.strip():
        raise ValidationError({"description": "Description is required before finishing this recipe."})

    breakdown_items = list(recipe.breakdown_items.all())
    # (issued materials/consumptions below are read fresh off the now-locked
    # recipe — not the cached prefetch from get_recipe_by_id — so the cost
    # calc reflects state as of this lock, not an earlier snapshot.)
    if not breakdown_items:
        raise ValidationError({"breakdown_items": "At least one breakdown item is required to finish this recipe."})

    total_cost = Decimal("0")
    for issued in recipe.issued_materials.all():
        for consumption in issued.consumptions.all():
            total_cost += consumption.quantity * consumption.unit_cost

    total_output_quantity = sum((item.quantity for item in breakdown_items), Decimal("0"))
    cost_per_unit = (
        (total_cost / total_output_quantity).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        if total_output_quantity > 0 else Decimal("0")
    )

    # cost_per_unit is a blended rate rounded to 4dp — stamping it as-is on
    # every item would make Σ(item.quantity × unit_cost_snapshot) drift from
    # the exact total_cost whenever the division doesn't come out even
    # (same rounding-order mistake as Jumbo/Packing purchase costing). Every
    # item but the last gets the blended rate; the last item absorbs
    # whatever's left of total_cost, so the sum reconciles exactly (down to
    # the field's own 4dp storage limit on that one item).
    remaining_cost = total_cost
    for item in breakdown_items[:-1]:
        item.unit_cost_snapshot = cost_per_unit
        remaining_cost -= item.quantity * cost_per_unit
    last_item = breakdown_items[-1]
    last_item.unit_cost_snapshot = (
        (remaining_cost / last_item.quantity).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        if last_item.quantity > 0 else Decimal("0")
    )
    RecipeBreakdownItem.objects.bulk_update(breakdown_items, ["unit_cost_snapshot"])

    recipe.status = Recipe.Status.FINISHED
    recipe.cost_per_unit = cost_per_unit
    recipe.finished_by = user
    recipe.finished_at = timezone.now()
    recipe.updated_by = user
    recipe.save(update_fields=["status", "cost_per_unit", "finished_by", "finished_at", "updated_by", "updated_at"])
    return recipe
