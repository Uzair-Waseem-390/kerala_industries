"""
WIP inventory writers — same role as inventory.services' sync_inventory /
apply_shelf_delta / apply_shelf_allocations, pointed at the WIP models
instead of RM's. Kept separate from services.py so the recipe business
logic there reads cleanly, same split purchases/services.py <-> inventory/services.py.
"""
from django.db import transaction

from .models import WipInventory, WipProduct, WipShelfStock, WipShelfStockMovement


def validate_wip_shelf_consumption(*, product: WipProduct, allocations: list[dict]) -> None:
    """
    WIP-equivalent of purchases.services.validate_shelf_consumption — every
    selected shelf must currently hold at least the requested quantity of
    this WIP product. Needed for Cutting's issue-time shelf picks (drawing
    WIP cores off a shelf, same as RM consumption does for Rewinding).
    Locks the rows it checks (called from within the caller's atomic block).
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
