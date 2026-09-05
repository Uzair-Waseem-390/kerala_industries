from django.db.models import QuerySet, Sum
from django.shortcuts import get_object_or_404

from backend.search import search_q
from production.utils import WIP_PRODUCT_SELECT_RELATED

from .models import (
    LOW_STOCK_THRESHOLD, Inventory, InventoryStatsFlow, ShelfStock,
    WipInventory, WipShelfStock,
)


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
    family_id   : str = None,
) -> QuerySet:
    """
    Returns inventory (global per-product total) with optional filters:
        search    : product name or product code (partial, case-insensitive)
        family_id : filter by the product's family
    Filtering by shelf no longer applies here — a product's stock can now
    span multiple shelves. Use get_shelf_stock_rows for "what's on shelf X".
    """
    # InventoryReadSerializer nests the full ProductReadSerializer (which in
    # turn nests family with its audit users) — without these, each row
    # costs extra queries (N+1).
    qs = Inventory.objects.select_related(
        "product", "last_updated_by",
        "product__created_by", "product__updated_by",
        "product__family", "product__family__created_by", "product__family__updated_by",
    ).filter(product__is_deleted=False)

    if _clean(search):
        qs = qs.filter(search_q(_clean(search), "product__name", "product__code"))
    if _clean(family_id):
        qs = qs.filter(product__family_id=_clean(family_id))

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


def get_low_stock_inventory(*, search: str = None, family_id: str = None) -> QuerySet:
    """
    Breakdown behind the "Low Stock" card: 0 < quantity <= LOW_STOCK_THRESHOLD.
    Same filters as the main inventory list; quantity is indexed.
    """
    return get_all_inventory(search=search, family_id=family_id).filter(
        quantity__gt=0, quantity__lte=LOW_STOCK_THRESHOLD,
    )


def get_out_of_stock_inventory(*, search: str = None, family_id: str = None) -> QuerySet:
    """
    Breakdown behind the "Out of Stock" card: quantity <= 0.
    Same filters as the main inventory list; quantity is indexed.
    """
    return get_all_inventory(search=search, family_id=family_id).filter(quantity__lte=0)


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


# ---------------------------------------------------------------------------
# WIP Inventory / Shelf Stock — moved here from production/selectors/
# rewinding.py and _shared.py (2026-09), alongside the WipInventory/
# WipShelfStock models themselves. production.WipProduct (the catalog)
# stays in production; these selectors just read the tracking tables here,
# same split as the RM section above (purchases.Product vs this app's
# Inventory/ShelfStock).
# ---------------------------------------------------------------------------

def get_all_wip_inventory(*, search: str = None, stage: str = None) -> QuerySet:
    # WipInventory itself has no is_deleted (it's not an AuditMixin model) —
    # explicitly excluding product__is_deleted here, since a soft-deleted
    # WipProduct's now-empty inventory row would otherwise still surface as
    # zero-quantity clutter.
    qs = WipInventory.objects.select_related(
        *[f"product__{f}" for f in WIP_PRODUCT_SELECT_RELATED], "product",
    ).filter(product__is_deleted=False)
    if _clean(stage):
        qs = qs.filter(product__stage=_clean(stage))
    if _clean(search):
        qs = qs.filter(search_q(_clean(search), "product__name"))
    return qs


def get_wip_shelf_stock_rows(shelf_id: int, *, search: str = None, stage: str = None) -> QuerySet:
    """
    WIP products + quantities currently on one shelf — powers the Shelf
    detail page's WIP tab. Mirrors get_shelf_stock_rows above exactly,
    pointed at WipShelfStock. Only "product" (id/name/stage) is read — same
    minimal-select_related reasoning as the RM version.
    """
    qs = WipShelfStock.objects.select_related("product").filter(
        shelf_id=shelf_id, quantity__gt=0, product__is_deleted=False,
    )
    if _clean(stage):
        qs = qs.filter(product__stage=_clean(stage))
    if _clean(search):
        qs = qs.filter(search_q(_clean(search), "product__name"))
    return qs.order_by("product__name")


def get_combined_inventory_rows(*, search: str = None, type_filter: str = None) -> list[dict]:
    """
    Every product's inventory row, RM and WIP alike, normalized into one
    flat shape and merged in Python. RM (`Inventory`) and WIP
    (`WipInventory`) are genuinely separate tables (different product
    catalogs, purchases.Product vs production.WipProduct — see
    instructions/multi-inventory-expansion.md's "structurally separate"
    principle), so there's no single queryset to filter/order — but the
    total row count is bounded by the number of distinct products in the
    business (never "all history", just a current snapshot), so merging
    the two already-filtered, already-indexed querysets in Python here is
    the same class of "genuinely bounded live aggregation" architecture.md
    allows for something like the Inventory Valuation report, not the
    unbounded live-merge pattern it warns against for growing event data.

    type_filter: 'raw_material' | 'wip_core' | 'wip_piece' | None (all).
    Pagination is handled by the caller (paginating this list directly,
    same as any DRF-paginated queryset).
    """
    rows: list[dict] = []

    if type_filter in (None, "raw_material"):
        for inv in get_all_inventory(search=search):
            rows.append({
                # RM and WIP products are independent auto-increment
                # sequences (separate tables) — a bare numeric id can
                # collide between the two, so the row id is namespaced.
                "id": f"rm-{inv.product_id}",
                "type": "raw_material",
                "name": inv.product.name,
                "code": inv.product.code,
                "category": inv.product.family.name if inv.product.family_id else None,
                "quantity": inv.quantity,
                "last_updated_at": inv.last_updated_at,
            })

    if type_filter in (None, "wip_core", "wip_piece"):
        wip_stage = {"wip_core": "rewinding", "wip_piece": "cutting"}.get(type_filter)
        for inv in get_all_wip_inventory(search=search, stage=wip_stage):
            rows.append({
                "id": f"wip-{inv.product_id}",
                "type": "wip_piece" if inv.product.stage == "cutting" else "wip_core",
                "name": inv.product.name,
                "code": None,
                "category": "WIP",
                "quantity": inv.quantity,
                "last_updated_at": inv.last_updated_at,
            })

    rows.sort(key=lambda r: r["name"])
    return rows


def get_candidate_shelves_for_wip_product(wip_product_id: int, *, search: str = None):
    """
    WIP-equivalent of purchases.selectors.get_candidate_shelves_for_product
    — shelves that currently hold stock (quantity > 0) of a given WIP product, for
    the consumption-side shelf picker (issuing a WIP core into a Cutting
    recipe, or increasing an already-issued quantity). Mirrors the RM
    version exactly, pointed at WipShelfStock via Shelf's "wip_stock_rows"
    related_name instead of RM's "stock_rows".
    """
    from purchases.models import Shelf

    qs = Shelf.objects.filter(
        is_deleted=False, wip_stock_rows__product_id=wip_product_id, wip_stock_rows__quantity__gt=0,
    )
    if _clean(search):
        qs = qs.filter(search_q(_clean(search), "name"))
    return qs.annotate(
        available_quantity=Sum("wip_stock_rows__quantity")
    ).order_by("name")
