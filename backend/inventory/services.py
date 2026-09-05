from django.db import transaction
from django.db.models import F
from django.utils import timezone

from purchases.models import Product, Shelf

from .models import (
    LOW_STOCK_THRESHOLD, Inventory, InventoryStatsFlow, ProductStockMovement,
    ShelfStock, ShelfStockMovement, StockMovementFlow, WipShelfStock, WipShelfStockMovement,
    WipInventory,
)


def _adjust_stock_movement(
    *, product_id: int,
    purchased_delta: int = 0,
    purchase_returned_delta: int = 0,
    sold_delta: int = 0,
    sale_returned_delta: int = 0,
    lost_delta: int = 0,
    found_delta: int = 0,
) -> None:
    """
    The ONLY function that writes to ProductStockMovement/StockMovementFlow
    — called from purchases (PO confirm, purchase return accept, lost
    inventory record, mark-as-found) and billing (invoice confirm, customer
    return accept) for the Stock Movement Report. All six fields only ever
    increase (none of the six source events are ever undone in this
    codebase), so no floor-at-0 logic is needed — plain PositiveIntegerField
    addition.

    Additions run inside the database via F() expressions, so two stock
    events committing at the same instant can never overwrite each other's
    counter update (the old read-add-save on the flow singleton could lose
    one side's addition). No row lock needed. .update() bypasses auto_now,
    hence last_updated_at is set explicitly — same field, same meaning.
    """
    deltas = {
        "total_purchased"        : purchased_delta,
        "total_purchase_returned": purchase_returned_delta,
        "total_sold"             : sold_delta,
        "total_sale_returned"    : sale_returned_delta,
        "total_lost"             : lost_delta,
        "total_found"            : found_delta,
    }
    with transaction.atomic():
        now = timezone.now()
        ProductStockMovement.objects.get_or_create(product_id=product_id)
        ProductStockMovement.objects.filter(product_id=product_id).update(
            last_updated_at=now,
            **{field: F(field) + delta for field, delta in deltas.items()},
        )

        StockMovementFlow.get_instance()
        StockMovementFlow.objects.filter(pk=1).update(
            last_updated_at=now,
            **{field: F(field) + delta for field, delta in deltas.items()},
        )


def _stock_bucket(quantity: int) -> str:
    """Maps a quantity to its stats bucket: 'out' / 'low' / 'ok'."""
    if quantity <= 0:
        return "out"
    if quantity <= LOW_STOCK_THRESHOLD:
        return "low"
    return "ok"


def _apply_inventory_stats_deltas(*, total_delta: int = 0, low_delta: int = 0, out_delta: int = 0) -> None:
    """
    Adjusts the InventoryStatsFlow singleton with F() expressions so the
    arithmetic happens inside the database — concurrent stock movements can
    never overwrite each other's counter updates.
    """
    if not (total_delta or low_delta or out_delta):
        return
    InventoryStatsFlow.get_instance()  # ensure the singleton row exists
    InventoryStatsFlow.objects.filter(pk=1).update(
        total_products     = F("total_products") + total_delta,
        low_stock_count    = F("low_stock_count") + low_delta,
        out_of_stock_count = F("out_of_stock_count") + out_delta,
        last_updated_at    = timezone.now(),
    )


_BUCKET_FIELD_DELTAS = {
    "out": {"out_delta": 1},
    "low": {"low_delta": 1},
    "ok" : {},
}


def _stats_deltas_for_transition(old_bucket: str | None, new_bucket: str) -> dict:
    """
    Counter deltas for a bucket transition. old_bucket=None means the
    inventory row was just created (also counts toward total_products).
    """
    deltas = {"total_delta": 0, "low_delta": 0, "out_delta": 0}
    if old_bucket == new_bucket:
        return deltas
    if old_bucket is None:
        deltas["total_delta"] = 1
    else:
        for key, value in _BUCKET_FIELD_DELTAS[old_bucket].items():
            deltas[key] -= value
    for key, value in _BUCKET_FIELD_DELTAS[new_bucket].items():
        deltas[key] += value
    return deltas


def sync_inventory(*, product: Product, quantity_delta: int, user=None) -> None:
    """
    THE single writer for Inventory.quantity — purchases AND billing must go
    through here (billing used to write quantity directly, which would let
    the stats counters drift). delta > 0 = increase, delta < 0 = decrease.
    Floored at 0 — inventory never goes negative. user=None leaves
    last_updated_by untouched (matches billing's return path, which never
    recorded a user).

    Also keeps InventoryStatsFlow in sync: when the new quantity crosses a
    low-stock/out-of-stock threshold, the singleton counters are adjusted in
    the same transaction. The row lock makes old_quantity trustworthy under
    concurrency, so a transition is never counted twice.
    """
    with transaction.atomic():
        inventory, created = (
            Inventory.objects.select_for_update().get_or_create(product=product)
        )
        old_bucket = None if created else _stock_bucket(inventory.quantity)

        inventory.quantity = max(0, inventory.quantity + quantity_delta)
        update_fields = ["quantity", "last_updated_at"]
        if user is not None:
            inventory.last_updated_by = user
            update_fields.append("last_updated_by")
        inventory.save(update_fields=update_fields)

        _apply_inventory_stats_deltas(
            **_stats_deltas_for_transition(old_bucket, _stock_bucket(inventory.quantity))
        )


def apply_shelf_delta(*, shelf: Shelf, product: Product, delta: int, reason: str, reference: str = "", user=None) -> None:
    """
    THE single writer for ShelfStock.quantity — every put-away/consumption/
    move funnels through here, mirroring sync_inventory's role for the
    global Inventory total. Locks the (shelf, product) row, floors at 0
    (defensive only — callers must validate availability before calling
    this for a negative delta via validate_shelf_consumption), and appends
    a ShelfStockMovement audit row in the same transaction.
    """
    with transaction.atomic():
        stock, _ = ShelfStock.objects.select_for_update().get_or_create(shelf=shelf, product=product)
        stock.quantity = max(0, stock.quantity + delta)
        stock.save(update_fields=["quantity", "last_updated_at"])
        ShelfStockMovement.objects.create(
            shelf=shelf, product=product, delta=delta,
            reason=reason, reference=reference, created_by=user,
        )


def apply_shelf_allocations(*, product: Product, allocations: list[dict], sign: int, reason: str, reference: str = "", user=None) -> None:
    """
    Applies a list of {"shelf": Shelf, "quantity": int} allocations for one
    product, each multiplied by `sign` (+1 for put-away, -1 for
    consumption). Locks shelves in deterministic (pk) order so two
    transactions touching overlapping shelf sets can never deadlock.

    Batched to a fixed small number of queries regardless of how many
    shelves this product's allocations span (one locking SELECT, one
    bulk_create for new rows, one bulk_update for existing rows, one
    bulk_create for the movement audit rows) instead of the previous
    per-shelf apply_shelf_delta() loop, which cost 3-4 sequential round
    trips PER SHELF — a purchase order with many multi-shelf lines could
    turn one confirm into hundreds of sequential queries. Same end state,
    same audit rows, same lock semantics — just fewer round trips.
    """
    if not allocations:
        return

    delta_by_shelf: dict[int, int] = {}
    shelf_by_id: dict[int, Shelf] = {}
    for allocation in allocations:
        shelf = allocation["shelf"]
        delta_by_shelf[shelf.pk] = delta_by_shelf.get(shelf.pk, 0) + sign * allocation["quantity"]
        shelf_by_id[shelf.pk] = shelf

    shelf_ids = sorted(delta_by_shelf.keys())
    now = timezone.now()

    with transaction.atomic():
        existing = {
            s.shelf_id: s
            for s in ShelfStock.objects.select_for_update()
                .filter(product=product, shelf_id__in=shelf_ids)
                .order_by("shelf_id")
        }
        to_create = []
        to_update = []
        movements = []
        for shelf_id in shelf_ids:
            delta = delta_by_shelf[shelf_id]
            stock = existing.get(shelf_id)
            if stock is None:
                to_create.append(ShelfStock(
                    shelf_id=shelf_id, product=product,
                    quantity=max(0, delta), last_updated_at=now,
                ))
            else:
                stock.quantity = max(0, stock.quantity + delta)
                stock.last_updated_at = now
                to_update.append(stock)
            movements.append(ShelfStockMovement(
                shelf_id=shelf_id, product=product, delta=delta,
                reason=reason, reference=reference, created_by=user,
            ))
        if to_create:
            ShelfStock.objects.bulk_create(to_create)
        if to_update:
            ShelfStock.objects.bulk_update(to_update, ["quantity", "last_updated_at"])
        ShelfStockMovement.objects.bulk_create(movements)


# ---------------------------------------------------------------------------
# WIP inventory writers — same role as sync_inventory/apply_shelf_allocations
# above, pointed at the WIP models instead of RM's. Moved here from
# production/wip_inventory.py (2026-09), alongside the WIP models
# themselves — "operate everything inventory-related from the inventory
# app" per project decision. `product` is a production.WipProduct instance;
# not imported here (avoids a circular production<->inventory import) since
# these functions only ever read product.pk/product.name off it.
# ---------------------------------------------------------------------------

def validate_wip_shelf_consumption(*, product, allocations: list[dict]) -> None:
    """
    WIP-equivalent of validate_shelf_consumption above — every selected
    shelf must currently hold at least the requested quantity of this WIP
    product. Needed for Cutting's issue-time shelf picks (drawing WIP cores
    off a shelf, same as RM consumption does for Rewinding). Locks the rows
    it checks (called from within the caller's atomic block).
    """
    from rest_framework.exceptions import ValidationError
    if not allocations:
        return

    shelf_by_id = {a["shelf"].pk: a["shelf"] for a in allocations}
    needed_by_id: dict[int, int] = {}
    for a in allocations:
        needed_by_id[a["shelf"].pk] = needed_by_id.get(a["shelf"].pk, 0) + a["quantity"]

    stock_by_shelf = {
        s.shelf_id: s.quantity
        for s in WipShelfStock.objects.select_for_update()
            .filter(product=product, shelf_id__in=sorted(needed_by_id.keys()))
            .order_by("shelf_id")
    }
    for shelf_id in sorted(needed_by_id.keys()):
        shelf = shelf_by_id[shelf_id]
        needed = needed_by_id[shelf_id]
        available = stock_by_shelf.get(shelf_id, 0)
        if available < needed:
            raise ValidationError({
                "shelf_allocations": (
                    f"Shelf '{shelf.name}' only has {available} of '{product.name}' "
                    f"available, but {needed} was requested. Select another shelf "
                    f"to cover the remaining {needed - available}."
                )
            })


def sync_wip_inventory(*, product, quantity_delta, user=None) -> None:
    """THE single writer for WipInventory.quantity. Floored at 0."""
    with transaction.atomic():
        inventory, _ = WipInventory.objects.select_for_update().get_or_create(product=product)
        inventory.quantity = max(0, inventory.quantity + quantity_delta)
        update_fields = ["quantity", "last_updated_at"]
        if user is not None:
            inventory.last_updated_by = user
            update_fields.append("last_updated_by")
        inventory.save(update_fields=update_fields)


def apply_wip_shelf_allocations(*, product, allocations: list[dict], sign: int, reason: str, reference: str = "", user=None) -> None:
    """
    Applies a list of {"shelf": Shelf, "quantity": Decimal} allocations for
    one WIP product, each multiplied by `sign` (+1 for put-away, -1 for
    consumption). Mirrors apply_shelf_allocations above exactly.
    """
    if not allocations:
        return

    delta_by_shelf = {}
    shelf_by_id = {}
    for allocation in allocations:
        shelf = allocation["shelf"]
        delta_by_shelf[shelf.pk] = delta_by_shelf.get(shelf.pk, 0) + sign * allocation["quantity"]
        shelf_by_id[shelf.pk] = shelf

    shelf_ids = sorted(delta_by_shelf.keys())
    now = timezone.now()

    with transaction.atomic():
        existing = {
            s.shelf_id: s
            for s in WipShelfStock.objects.select_for_update()
                .filter(product=product, shelf_id__in=shelf_ids)
                .order_by("shelf_id")
        }
        to_create = []
        to_update = []
        movements = []
        for shelf_id in shelf_ids:
            delta = delta_by_shelf[shelf_id]
            stock = existing.get(shelf_id)
            if stock is None:
                to_create.append(WipShelfStock(shelf_id=shelf_id, product=product, quantity=max(0, delta)))
            else:
                stock.quantity = max(0, stock.quantity + delta)
                stock.last_updated_at = now
                to_update.append(stock)
            movements.append(WipShelfStockMovement(
                shelf_id=shelf_id, product=product, delta=delta,
                reason=reason, reference=reference, created_by=user,
            ))

        if to_create:
            WipShelfStock.objects.bulk_create(to_create)
        if to_update:
            WipShelfStock.objects.bulk_update(to_update, ["quantity", "last_updated_at"])
        WipShelfStockMovement.objects.bulk_create(movements)
