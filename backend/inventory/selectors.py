from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

from backend.search import search_q

from .models import LOW_STOCK_THRESHOLD, Inventory, InventoryStatsFlow, ShelfStock


def _clean(value):
    """Returns None if value is None or empty/whitespace string, else stripped value."""
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped if stripped else None


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

def get_all_inventory(
    *,
    search      : str = None,
) -> QuerySet:
    """
    Returns inventory (global per-product total) with optional filters:
        search : product name or product code (partial, case-insensitive)
    Filtering by shelf no longer applies here — a product's stock can now
    span multiple shelves. Use get_shelf_stock_rows for "what's on shelf X".
    """
    # InventoryReadSerializer nests the full ProductReadSerializer — without
    # these, each row costs extra queries (N+1).
    qs = Inventory.objects.select_related(
        "product", "last_updated_by",
        "product__created_by", "product__updated_by",
    ).filter(product__is_deleted=False)

    if _clean(search):
        qs = qs.filter(search_q(_clean(search), "product__name", "product__code"))

    return qs.order_by("product__name")


def get_inventory_by_product_id(product_id: int) -> Inventory:
    return get_object_or_404(
        Inventory.objects.select_related("product"),
        product_id=product_id,
    )


def get_inventory_stats() -> InventoryStatsFlow:
    """
    O(1) inventory stats for the Inventory page cards — reads the stored
    singleton instead of counting rows. Kept in sync at write time by
    services.sync_inventory()/delete_product(); rebuilt by
    backfill_inventory_stats.
    """
    return InventoryStatsFlow.get_instance()


def get_low_stock_inventory(*, search: str = None) -> QuerySet:
    """
    Breakdown behind the "Low Stock" card: 0 < quantity <= LOW_STOCK_THRESHOLD.
    Same filters as the main inventory list; quantity is indexed.
    """
    return get_all_inventory(search=search).filter(quantity__gt=0, quantity__lte=LOW_STOCK_THRESHOLD)


def get_out_of_stock_inventory(*, search: str = None) -> QuerySet:
    """
    Breakdown behind the "Out of Stock" card: quantity <= 0.
    Same filters as the main inventory list; quantity is indexed.
    """
    return get_all_inventory(search=search).filter(quantity__lte=0)


# ---------------------------------------------------------------------------
# Shelf stock (per-location breakdown)
# ---------------------------------------------------------------------------

def get_shelf_stock_rows(shelf_id: int, *, search: str = None) -> QuerySet:
    """
    Products + quantities currently on one shelf — feeds the shelf detail
    page (click a shelf → see its contents). Only rows with quantity > 0
    are shown; a product that was fully moved/consumed off a shelf leaves
    no trace here (ShelfStockMovement is the audit trail for that).
    """
    # Only "product" is actually read (ShelfStockReadSerializer nests
    # ProductLiteSerializer: id/name/code only) — category/created_by/
    # updated_by were an unnecessary 3-way JOIN on every row.
    qs = ShelfStock.objects.select_related("product").filter(shelf_id=shelf_id, quantity__gt=0)
    if _clean(search):
        qs = qs.filter(search_q(_clean(search), "product__name", "product__code"))
    return qs.order_by("product__name")
