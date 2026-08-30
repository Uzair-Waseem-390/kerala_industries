"""
WIP inventory writers — same role as inventory.services' sync_inventory /
apply_shelf_delta / apply_shelf_allocations, pointed at the WIP models
instead of RM's. Kept separate from services.py so the recipe business
logic there reads cleanly, same split purchases/services.py <-> inventory/services.py.
"""
from django.db import transaction

from .models import WipInventory, WipProduct, WipShelfStock, WipShelfStockMovement


def sync_wip_inventory(*, product: WipProduct, quantity_delta, user=None) -> None:
    """THE single writer for WipInventory.quantity. Floored at 0."""
    with transaction.atomic():
        inventory, _ = WipInventory.objects.select_for_update().get_or_create(product=product)
        inventory.quantity = max(0, inventory.quantity + quantity_delta)
        update_fields = ["quantity", "last_updated_at"]
        if user is not None:
            inventory.last_updated_by = user
            update_fields.append("last_updated_by")
        inventory.save(update_fields=update_fields)


def apply_wip_shelf_allocations(*, product: WipProduct, allocations: list[dict], sign: int, reason: str, reference: str = "", user=None) -> None:
    """
    Applies a list of {"shelf": Shelf, "quantity": Decimal} allocations for
    one WIP product, each multiplied by `sign` (+1 for put-away, -1 for
    consumption). Mirrors inventory.services.apply_shelf_allocations exactly.
    """
    if not allocations:
        return

    from django.utils import timezone

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
