from .models import (
    CustomerOpeningBalance, OpeningCashEntry, SupplierOpeningBalance,
)


# ---------------------------------------------------------------------------
# Audit list selectors (superuser GET endpoints)
# ---------------------------------------------------------------------------

def get_all_supplier_opening_balances():
    return SupplierOpeningBalance.objects.select_related(
        "supplier", "purchase_order", "created_by",
    ).order_by("-created_at")


def get_all_customer_opening_balances():
    return CustomerOpeningBalance.objects.select_related(
        "customer", "invoice", "created_by",
    ).order_by("-created_at")


def get_all_opening_cash_entries():
    return OpeningCashEntry.objects.select_related("added_by").order_by("-added_at")


def get_all_opening_stock_orders():
    from purchases.models import PurchaseOrder
    return (
        PurchaseOrder.objects
        .filter(is_data_entry=True, supplier__code="SYS-OPENING", is_deleted=False)
        .select_related("supplier")
        .prefetch_related("items__product")
        .order_by("-created_at")
    )


def get_all_opening_wip_stock_recipes():
    """
    Opening WIP stock recipes (2026-09) — real production.Recipe rows
    (is_data_entry=True, recipe_type=REWINDING — see production.services
    .opening_stock.create_opening_wip_stock, which always creates that
    type regardless of whether the items inside are core or piece stage).
    Prefetches both possible child tables since a single call can mix
    stages within one recipe.
    """
    from production.models import CuttingBreakdownItem, Recipe, RecipeBreakdownItem
    return (
        Recipe.objects
        .filter(is_data_entry=True, recipe_type=Recipe.RecipeType.REWINDING, is_deleted=False)
        .prefetch_related(
            "breakdown_items__wip_product",
            "cutting_breakdown_items__wip_product",
        )
        .order_by("-created_at")
    )


def get_all_opening_fg_stock_recipes():
    """Opening FG stock recipes (2026-09) — one Recipe per item, see
    production.services.opening_stock.create_opening_fg_stock's docstring
    for why (PackingOutputItem.recipe is a OneToOneField)."""
    from production.models import Recipe
    return (
        Recipe.objects
        .filter(is_data_entry=True, recipe_type=Recipe.RecipeType.PACKING, is_deleted=False)
        .select_related("packing_output_item__fg_product")
        .order_by("-created_at")
    )


def get_all_opening_investor_investments():
    from cash_management.models import InvestorTransaction
    return (
        InvestorTransaction.objects
        .filter(is_data_entry=True, is_deleted=False)
        .select_related("investor", "created_by")
        .order_by("-created_at")
    )
