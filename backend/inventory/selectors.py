from decimal import Decimal

from django.db.models import Case, DateTimeField, DecimalField, Q, QuerySet, Sum, Value, When
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404

from backend.search import search_q
from production.utils import WIP_PRODUCT_SELECT_RELATED

from .models import (
    LOW_STOCK_THRESHOLD, FgInventory, FgInventoryStatsFlow, FgShelfStock,
    Inventory, InventoryStatsFlow, ProductRegistryEntry, ShelfStock,
    WipInventory, WipInventoryStatsFlow, WipShelfStock,
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


def get_wip_inventory_stats() -> WipInventoryStatsFlow:
    """O(1) WIP inventory stats — WIP-side twin of get_inventory_stats."""
    return WipInventoryStatsFlow.get_instance()


def get_fg_inventory_stats() -> FgInventoryStatsFlow:
    """O(1) FG inventory stats — FG-side twin of get_inventory_stats."""
    return FgInventoryStatsFlow.get_instance()


def get_combined_inventory_stats() -> dict:
    """
    O(1) stats for the All Inventory page header — three singleton reads
    added together, never a live count/sum. Every source singleton is
    itself O(1) (see get_inventory_stats/get_wip_inventory_stats/
    get_fg_inventory_stats), so this stays O(1) regardless of how many
    products exist.
    """
    rm = get_inventory_stats()
    wip = get_wip_inventory_stats()
    fg = get_fg_inventory_stats()
    return {
        "total_products"     : rm.total_products + wip.total_products + fg.total_products,
        "total_stock"        : rm.total_stock + wip.total_stock + fg.total_stock,
        "low_stock_count"    : rm.low_stock_count + wip.low_stock_count + fg.low_stock_count,
        "out_of_stock_count" : rm.out_of_stock_count + wip.out_of_stock_count + fg.out_of_stock_count,
        "last_updated_at"    : max(rm.last_updated_at, wip.last_updated_at, fg.last_updated_at),
    }


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


def get_low_stock_wip_inventory(*, search: str = None, stage: str = None) -> QuerySet:
    """Breakdown behind the "Low Stock" card for WIP — WIP-side twin of get_low_stock_inventory."""
    return get_all_wip_inventory(search=search, stage=stage).filter(
        quantity__gt=0, quantity__lte=LOW_STOCK_THRESHOLD,
    )


def get_out_of_stock_wip_inventory(*, search: str = None, stage: str = None) -> QuerySet:
    """Breakdown behind the "Out of Stock" card for WIP — WIP-side twin of get_out_of_stock_inventory."""
    return get_all_wip_inventory(search=search, stage=stage).filter(quantity__lte=0)


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


def get_all_registry_products(*, search: str = None, type_filter: str = None, stock_view: str = None) -> QuerySet:
    """
    Every product's identity row, RM/WIP/FG alike, as ONE real queryset —
    replaces the old get_combined_inventory_rows, which fully materialized
    and Python-sorted 3 separately-fetched querysets on every request
    (O(catalog size) regardless of page requested). ProductRegistryEntry is
    a pure identity index (see its docstring); `quantity`/`last_updated_at`
    are fetched live via a conditional join to whichever stage's own
    Inventory table applies per row (Case/When on `type`) — never
    denormalized onto the registry itself, so there's no new place that
    needs to stay in sync on every stock movement.

    Soft-deleted products are excluded the same way the old per-type
    selectors did (product__is_deleted=False), just via a join here instead
    of starting from the Inventory table.

    type_filter: 'raw_material' | 'wip_core' | 'wip_piece' | 'finished_goods' | None (all).
    stock_view: 'low' | 'out' | None (all) — same Low Stock/Out of Stock
    breakdown as before. Filtering on the Case/When quantity here doesn't
    use each stage's own quantity index the way filtering the original
    per-stage queryset directly would (the DB evaluates the CASE per
    matched row rather than range-scanning one column) — acceptable given
    the same "genuinely bounded by product count" reasoning architecture.md
    already accepts for this catalog (never "all history"), and this
    is still one real query with `type` pushed down via an index, not a
    live count (the COUNTS themselves stay O(1) via get_combined_inventory_stats,
    untouched by this). ORDER BY + LIMIT/OFFSET (applied by the caller's
    pagination) run at the database, not in Python.

    quantity is Coalesce'd to 0 — an RM variant's registry row is written
    at product-creation time (get_or_create_product_variant, when a draft
    purchase order is created), but its Inventory row isn't created until
    sync_inventory first runs at PurchaseOrder confirm — a real gap (a
    draft that's never confirmed, or gets deleted, leaves a registry row
    with no matching Inventory row, permanently). Without the Coalesce,
    that row's quantity annotation is NULL: invisible from BOTH
    stock_view=low (NULL > 0 is false) and stock_view=out (NULL <= 0 is
    also false) while showing `quantity: null` on "All" — found by audit.
    Zero is the semantically correct value here anyway (no confirmed stock
    movement has ever touched this product), matching Inventory.quantity's
    own default=0 for a freshly-created row.
    """
    zero = Value(Decimal("0"), output_field=DecimalField(max_digits=14, decimal_places=4))
    qs = ProductRegistryEntry.objects.filter(
        Q(type=ProductRegistryEntry.Type.RAW_MATERIAL, rm_product__is_deleted=False) |
        Q(type__in=[ProductRegistryEntry.Type.WIP_CORE, ProductRegistryEntry.Type.WIP_PIECE], wip_product__is_deleted=False) |
        Q(type=ProductRegistryEntry.Type.FINISHED_GOODS, fg_product__is_deleted=False)
    ).annotate(
        quantity=Coalesce(Case(
            When(type=ProductRegistryEntry.Type.RAW_MATERIAL, then="rm_product__inventory__quantity"),
            When(type__in=[ProductRegistryEntry.Type.WIP_CORE, ProductRegistryEntry.Type.WIP_PIECE], then="wip_product__inventory__quantity"),
            When(type=ProductRegistryEntry.Type.FINISHED_GOODS, then="fg_product__inventory__quantity"),
            output_field=DecimalField(max_digits=14, decimal_places=4),
        ), zero),
        last_updated_at=Case(
            When(type=ProductRegistryEntry.Type.RAW_MATERIAL, then="rm_product__inventory__last_updated_at"),
            When(type__in=[ProductRegistryEntry.Type.WIP_CORE, ProductRegistryEntry.Type.WIP_PIECE], then="wip_product__inventory__last_updated_at"),
            When(type=ProductRegistryEntry.Type.FINISHED_GOODS, then="fg_product__inventory__last_updated_at"),
            output_field=DateTimeField(),
        ),
    )

    if type_filter:
        qs = qs.filter(type=type_filter)
    if _clean(search):
        qs = qs.filter(search_q(_clean(search), "name", "code"))
    if stock_view == "low":
        qs = qs.filter(quantity__gt=0, quantity__lte=LOW_STOCK_THRESHOLD)
    elif stock_view == "out":
        qs = qs.filter(quantity__lte=0)

    return qs.order_by("name")


# ---------------------------------------------------------------------------
# FG Inventory / Shelf Stock — mirrors the WIP section above exactly, pointed
# at the FG models. production.FgProduct (the catalog) stays in production;
# these selectors just read the tracking tables here.
# ---------------------------------------------------------------------------

def get_all_fg_inventory(*, search: str = None) -> QuerySet:
    qs = FgInventory.objects.select_related(
        "product", "product__binding", "product__yard", "product__length_mm",
    ).filter(product__is_deleted=False)
    if _clean(search):
        qs = qs.filter(search_q(_clean(search), "product__name"))
    return qs


def get_low_stock_fg_inventory(*, search: str = None) -> QuerySet:
    """Breakdown behind the "Low Stock" card for FG — FG-side twin of get_low_stock_inventory."""
    return get_all_fg_inventory(search=search).filter(quantity__gt=0, quantity__lte=LOW_STOCK_THRESHOLD)


def get_out_of_stock_fg_inventory(*, search: str = None) -> QuerySet:
    """Breakdown behind the "Out of Stock" card for FG — FG-side twin of get_out_of_stock_inventory."""
    return get_all_fg_inventory(search=search).filter(quantity__lte=0)


def get_fg_shelf_stock_rows(shelf_id: int, *, search: str = None) -> QuerySet:
    """FG products + quantities currently on one shelf — mirrors get_wip_shelf_stock_rows."""
    qs = FgShelfStock.objects.select_related("product").filter(
        shelf_id=shelf_id, quantity__gt=0, product__is_deleted=False,
    )
    if _clean(search):
        qs = qs.filter(search_q(_clean(search), "product__name"))
    return qs.order_by("product__name")


def get_candidate_shelves_for_fg_product(fg_product_id: int, *, search: str = None):
    """FG-equivalent of get_candidate_shelves_for_wip_product above, pointed at Shelf's "fg_stock_rows" related_name."""
    from purchases.models import Shelf

    qs = Shelf.objects.filter(
        is_deleted=False, fg_stock_rows__product_id=fg_product_id, fg_stock_rows__quantity__gt=0,
    )
    if _clean(search):
        qs = qs.filter(search_q(_clean(search), "name"))
    return qs.annotate(
        available_quantity=Sum("fg_stock_rows__quantity")
    ).order_by("name")


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
