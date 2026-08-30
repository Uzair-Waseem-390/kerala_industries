from django.conf import settings
from django.db import models


# ---------------------------------------------------------------------------
# Inventory (auto-managed — unchanged)
#
# Mechanically relocated from purchases/models.py — same tables, same
# fields, same behavior. Meta.db_table is pinned to the ORIGINAL table name
# (purchases_<modelname>) so this move is a pure Django state relabel, not a
# real table rename — see the paired migrations in this app and in
# purchases for the SeparateDatabaseAndState pattern used.
# ---------------------------------------------------------------------------

class Inventory(models.Model):
    product         = models.OneToOneField("purchases.Product", on_delete=models.PROTECT, related_name="inventory")
    # Indexed — the low-stock / out-of-stock breakdown endpoints filter on
    # quantity thresholds.
    quantity        = models.DecimalField(max_digits=14, decimal_places=4, default=0, db_index=True)
    last_updated_at = models.DateTimeField(auto_now=True)
    last_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="inventory_updates",
    )

    class Meta:
        db_table             = "purchases_inventory"
        verbose_name        = "Inventory"
        verbose_name_plural = "Inventories"
        ordering            = ["product__name"]

    def __str__(self):
        return f"{self.product.name} — qty: {self.quantity}"


class ShelfStock(models.Model):
    """
    Live physical quantity of one product on one shelf. This is the
    per-location breakdown of the same total tracked globally by
    Inventory.quantity — the two must always agree in total
    (sum(ShelfStock.quantity for product) == Inventory.quantity for that
    product). Only ever mutated through services.apply_shelf_delta (the
    single writer, mirroring sync_inventory's role for Inventory).
    """
    shelf           = models.ForeignKey("purchases.Shelf", on_delete=models.PROTECT, related_name="stock_rows")
    product         = models.ForeignKey("purchases.Product", on_delete=models.PROTECT, related_name="shelf_stock_rows")
    quantity        = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    last_updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table             = "purchases_shelfstock"
        verbose_name        = "Shelf Stock"
        verbose_name_plural = "Shelf Stock"
        unique_together     = [("shelf", "product")]

    def __str__(self):
        return f"{self.shelf.name} — {self.product.name}: {self.quantity}"


class ShelfStockMovement(models.Model):
    """
    Append-only audit ledger — one row per shelf-quantity change, whatever
    caused it. This is the human-readable trail behind every ShelfStock
    number: which purchase/sale/return/loss/move touched this shelf, when,
    by whom. Never read for live totals (ShelfStock.quantity is the O(1)
    stored figure) — this is drill-down/audit only.
    """
    class Reason(models.TextChoices):
        PURCHASE_PUTAWAY     = "purchase_putaway",     "Purchase Put-Away"
        SALE_CONSUMPTION     = "sale_consumption",     "Sale Consumption"
        INVOICE_RETURN_PUTAWAY = "invoice_return_putaway", "Invoice Return Put-Away"
        PURCHASE_RETURN_CONSUMPTION = "purchase_return_consumption", "Purchase Return Consumption"
        LOST_CONSUMPTION     = "lost_consumption",     "Lost Inventory Consumption"
        LOST_FOUND_PUTAWAY   = "lost_found_putaway",   "Lost Inventory Found Put-Away"
        MOVE_OUT             = "move_out",             "Manual Move (Out)"
        MOVE_IN              = "move_in",              "Manual Move (In)"
        JUMBO_LENGTH_CORRECTION = "jumbo_length_correction", "Jumbo Exact-Length Correction"
        RECIPE_ISSUE_CONSUMPTION = "recipe_issue_consumption", "Recipe Material Issue"
        BACKFILL             = "backfill",              "Backfill"

    shelf      = models.ForeignKey("purchases.Shelf", on_delete=models.PROTECT, related_name="movements")
    product    = models.ForeignKey("purchases.Product", on_delete=models.PROTECT, related_name="shelf_movements")
    delta      = models.DecimalField(max_digits=14, decimal_places=4, help_text="Positive = added to shelf, negative = removed from shelf.")
    reason     = models.CharField(max_length=30, choices=Reason.choices, db_index=True)
    reference  = models.CharField(max_length=30, blank=True, default="", help_text="e.g. PO-2026-0001, BILL-2026-0001")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="shelf_stock_movements",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table             = "purchases_shelfstockmovement"
        verbose_name        = "Shelf Stock Movement"
        verbose_name_plural = "Shelf Stock Movements"
        ordering            = ["-created_at"]
        indexes = [
            models.Index(fields=["shelf", "-created_at"]),
            models.Index(fields=["product", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.shelf.name} — {self.product.name}: {self.delta:+} ({self.reason})"


class ProductStockMovement(models.Model):
    """
    Per-product running quantity totals for the Stock Movement Report —
    one row per product, updated live via _adjust_stock_movement() in
    services.py. All six fields only ever increase: none of the six
    source events (PO confirm, purchase return accept, invoice confirm,
    customer return accept, lost inventory record, mark-as-found) are
    ever undone in this codebase.
    """
    product                 = models.OneToOneField("purchases.Product", on_delete=models.CASCADE, related_name="stock_movement")
    total_purchased         = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    total_purchase_returned = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    total_sold               = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    total_sale_returned      = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    total_lost                = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    total_found               = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    last_updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        db_table             = "purchases_productstockmovement"
        verbose_name        = "Product Stock Movement"
        verbose_name_plural = "Product Stock Movement"

    def __str__(self):
        return f"{self.product.name} — purchased {self.total_purchased}, sold {self.total_sold}"


class StockMovementFlow(models.Model):
    """
    Single live record — the all-time, all-product totals for the Stock
    Movement Report header. Same six fields as ProductStockMovement,
    summed across every product, kept in sync by the same
    _adjust_stock_movement() calls.
    """
    total_purchased         = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    total_purchase_returned = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    total_sold               = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    total_sale_returned      = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    total_lost                = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    total_found               = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    last_updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        db_table             = "purchases_stockmovementflow"
        verbose_name        = "Stock Movement Flow"
        verbose_name_plural = "Stock Movement Flow"

    def __str__(self):
        return f"StockMovementFlow — purchased {self.total_purchased}, sold {self.total_sold}"

    @classmethod
    def get_instance(cls):
        instance, _ = cls.objects.get_or_create(pk=1)
        return instance


# Products with 0 < quantity <= LOW_STOCK_THRESHOLD count as "low stock";
# quantity <= 0 counts as "out of stock". Single source of truth for the
# stats singleton, the breakdown selectors, and the backfill command.
LOW_STOCK_THRESHOLD = 5


class InventoryStatsFlow(models.Model):
    """
    Single live record — O(1) inventory stats for the Inventory page cards
    (total products, low stock, out of stock). Counts cover inventory rows
    of non-deleted products only, matching what the inventory list shows.
    Kept in sync by services.sync_inventory() (the ONLY quantity writer,
    used by purchases AND billing) and services.delete_product(); rebuilt
    from live data by backfill_inventory_stats.
    """
    total_products     = models.PositiveIntegerField(default=0)
    low_stock_count    = models.PositiveIntegerField(default=0)
    out_of_stock_count = models.PositiveIntegerField(default=0)
    last_updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table             = "purchases_inventorystatsflow"
        verbose_name        = "Inventory Stats Flow"
        verbose_name_plural = "Inventory Stats Flow"

    def __str__(self):
        return (
            f"InventoryStatsFlow — total {self.total_products}, "
            f"low {self.low_stock_count}, out {self.out_of_stock_count}"
        )

    @classmethod
    def get_instance(cls):
        instance, _ = cls.objects.get_or_create(pk=1)
        return instance
