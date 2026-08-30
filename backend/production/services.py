from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from inventory.models import ShelfStockMovement
from inventory.services import apply_shelf_allocations as apply_rm_shelf_allocations
from inventory.services import sync_inventory as sync_rm_inventory
from purchases.models import CORES_PRODUCT_CODE, Family, JUMBO_PRODUCT_CODE
from purchases.selectors import get_available_purchase_items_for_fifo, get_product_by_id
from purchases.services import (
    _unique_constraint_guard, _validate_shelf_ids_exist, next_reference,
    validate_allocations_complete, validate_shelf_consumption,
)

from .models import (
    Recipe, RecipeBreakdownItem, RecipeIssuedMaterial, RecipeMaterialConsumption,
    RewoundCoreBinding, RewoundCoreLengthMm, RewoundCoreYard, WipProduct, WipShelfStockMovement,
)
from .selectors import get_issued_material
from .utils import compute_wip_variant_key, inches_to_mm
from .wip_inventory import apply_wip_shelf_allocations, sync_wip_inventory


def _next_recipe_number() -> str:
    return next_reference(counter_key="REC", prefix_label="REC", model=Recipe, field="recipe_number")


def _fmt(value: Decimal) -> str:
    """'100.0000' -> '100', '1295.4000' -> '1295.4' — no trailing zeros/decimal point."""
    s = format(value, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


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
def create_recipe(*, name: str, description: str, recipe_type: str = Recipe.RecipeType.REWINDING, user) -> Recipe:
    from rest_framework.exceptions import ValidationError
    if not name or not name.strip():
        raise ValidationError({"name": "Name is required."})
    if not description or not description.strip():
        raise ValidationError({"description": "Description is required."})

    return Recipe.objects.create(
        recipe_number=_next_recipe_number(),
        recipe_type=recipe_type,
        name=name.strip(),
        description=description.strip(),
        created_by=user, updated_by=user,
    )


def _get_locked_recipe(recipe_id: int) -> Recipe:
    """
    Locks the Recipe row before any status check — every mutating service
    function must call this FIRST, inside its own @transaction.atomic. A
    plain unlocked read-then-check (the earlier version of this function)
    lets two concurrent requests both pass a status check before either
    commits its state change (e.g. two overlapping "Finish" clicks, or a
    finish racing an add-breakdown-item) — the row lock serializes them so
    the second request re-reads the true post-commit status.
    """
    from django.shortcuts import get_object_or_404
    return get_object_or_404(Recipe.objects.select_for_update(), pk=recipe_id, is_deleted=False)


def _require_under_processing(recipe: Recipe) -> None:
    from rest_framework.exceptions import ValidationError
    if recipe.status != Recipe.Status.UNDER_PROCESSING:
        raise ValidationError({"status": "This recipe is finished and can no longer be edited."})


def _validate_material_kind_matches_product(*, kind: str, product) -> None:
    from rest_framework.exceptions import ValidationError
    expected_code = JUMBO_PRODUCT_CODE if kind == RecipeIssuedMaterial.MaterialKind.JUMBO else CORES_PRODUCT_CODE
    if product.base_product_id is None or product.base_product.code != expected_code:
        raise ValidationError({
            "product_id": f"'{product.name}' is not a {kind} variant with attributes selected."
        })


def _normalize_shelf_allocations(allocations: list[dict], *, required_total: Decimal, field_label: str = "shelf_allocations"):
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


def _draw_fifo(*, issued_material: RecipeIssuedMaterial, quantity: Decimal, user) -> None:
    """
    Consumes `quantity` of issued_material.product from RM purchase batches,
    oldest first — same mechanism as billing._run_fifo. Records one
    RecipeMaterialConsumption row per batch drawn from and decrements each
    batch's remaining_quantity. Raises if RM doesn't have enough stock left
    (should not happen if the caller already checked Inventory.quantity, but
    the locked re-walk here is the trustworthy check under concurrency).
    """
    from rest_framework.exceptions import ValidationError

    remaining_to_consume = quantity
    batches = get_available_purchase_items_for_fifo(issued_material.product_id, for_update=True)

    for batch in batches:
        if remaining_to_consume <= 0:
            break
        consume = min(batch.remaining_quantity, remaining_to_consume)
        unit_cost = (batch.total_price / batch.quantity) if batch.quantity > 0 else batch.unit_price

        RecipeMaterialConsumption.objects.create(
            issued_material=issued_material, purchase_item=batch,
            quantity=consume, unit_cost=unit_cost,
        )
        batch.remaining_quantity -= consume
        batch.save(update_fields=["remaining_quantity"])
        remaining_to_consume -= consume

    if remaining_to_consume > 0:
        raise ValidationError({
            "quantity": (
                f"Stock ran out mid-issue for '{issued_material.product.name}' — "
                f"{remaining_to_consume} short. Please refresh and try again."
            )
        })


def _return_fifo(*, issued_material: RecipeIssuedMaterial, quantity: Decimal) -> None:
    """
    Reverses `quantity` worth of this issued_material's consumption,
    most-recently-drawn batch first — the inverse of _draw_fifo. Restores
    remaining_quantity on each affected PurchaseItem and shrinks/deletes the
    RecipeMaterialConsumption row accordingly.

    Batches are located (by LIFO consumption order) WITHOUT locking first,
    then locked in ONE query ordered exactly the way _draw_fifo locks them
    (oldest-confirmed-first) before any row is mutated. Locking them
    one-by-one in LIFO order — the previous version of this function — would
    let a concurrent increase (which locks oldest-first via _draw_fifo) and
    a concurrent decrease on the same issued material lock the same two
    batches in opposite order: a textbook circular-wait deadlock. Locking
    everything up front, in the same order every caller uses, also drops
    the redundant per-row re-lock the old version did (the join below
    already gives us the row; we don't need to fetch it again).
    """
    from purchases.models import PurchaseItem
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

    batch_ids = {c.purchase_item_id for c, _ in candidates}
    locked_batches = {
        b.pk: b
        for b in PurchaseItem.objects.select_for_update()
            .filter(pk__in=batch_ids).order_by("order__confirmed_at", "pk")
    }

    for consumption, give_back in candidates:
        locked_batch = locked_batches[consumption.purchase_item_id]
        locked_batch.remaining_quantity += give_back
        locked_batch.save(update_fields=["remaining_quantity"])

        if give_back == consumption.quantity:
            consumption.delete()
        else:
            consumption.quantity -= give_back
            consumption.save(update_fields=["quantity"])


# ---------------------------------------------------------------------------
# Issue / update RM material
# ---------------------------------------------------------------------------

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

    variant_key = compute_wip_variant_key(binding_id=binding.id, yard_id=yard_lookup.id, length_mm_id=length_lookup.id)
    wip_product = WipProduct.objects.filter(variant_key=variant_key).first()
    if wip_product is None:
        wip_family = Family.objects.get(name="WIP")
        name = f"{binding.value} {_fmt(yard_lookup.value)} yard {_fmt(length_lookup.value)}"
        try:
            with transaction.atomic():
                wip_product = WipProduct.objects.create(
                    name=name, family=wip_family, binding=binding, yard=yard_lookup, length_mm=length_lookup,
                    variant_key=variant_key, created_by=user, updated_by=user,
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
    return item


@transaction.atomic
def finish_recipe(*, recipe_id: int, user) -> Recipe:
    from rest_framework.exceptions import ValidationError

    recipe = _get_locked_recipe(recipe_id)
    _require_under_processing(recipe)

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
    cost_per_unit = (total_cost / total_output_quantity).quantize(Decimal("0.0001")) if total_output_quantity > 0 else Decimal("0")

    for item in breakdown_items:
        item.unit_cost_snapshot = cost_per_unit
    RecipeBreakdownItem.objects.bulk_update(breakdown_items, ["unit_cost_snapshot"])

    recipe.status = Recipe.Status.FINISHED
    recipe.cost_per_unit = cost_per_unit
    recipe.finished_by = user
    recipe.finished_at = timezone.now()
    recipe.updated_by = user
    recipe.save(update_fields=["status", "cost_per_unit", "finished_by", "finished_at", "updated_by", "updated_at"])
    return recipe
