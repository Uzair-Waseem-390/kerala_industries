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


# ---------------------------------------------------------------------------
# WIP Inventory (mechanically relocated from production/models.py, 2026-09)
#
# Same pattern as the RM move above: Meta.db_table is pinned to the
# ORIGINAL table name (production_<modelname>) so this is a pure Django
# state relabel, not a real table rename — see the paired
# SeparateDatabaseAndState migrations in this app and in production.
# WipProduct itself (the WIP catalog: name, binding/yard/length_mm
# attributes) stays in production, mirroring how purchases.Product (the RM
# catalog) stays in purchases while the tracking tables live here.
# ---------------------------------------------------------------------------

class WipInventory(models.Model):
    product         = models.OneToOneField("production.WipProduct", on_delete=models.PROTECT, related_name="inventory")
    quantity        = models.DecimalField(max_digits=14, decimal_places=4, default=0, db_index=True)
    last_updated_at = models.DateTimeField(auto_now=True)
    last_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="wip_inventory_updates",
    )

    class Meta:
        db_table            = "production_wipinventory"
        verbose_name        = "WIP Inventory"
        verbose_name_plural = "WIP Inventories"
        ordering            = ["product__name"]

    def __str__(self):
        return f"{self.product.name} — qty: {self.quantity}"


class WipShelfStock(models.Model):
    """Live physical quantity of one WIP product on one shelf — WIP-side twin of ShelfStock."""
    shelf           = models.ForeignKey("purchases.Shelf", on_delete=models.PROTECT, related_name="wip_stock_rows")
    product         = models.ForeignKey("production.WipProduct", on_delete=models.PROTECT, related_name="shelf_stock_rows")
    quantity        = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    last_updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table            = "production_wipshelfstock"
        verbose_name        = "WIP Shelf Stock"
        verbose_name_plural = "WIP Shelf Stock"
        unique_together     = [("shelf", "product")]

    def __str__(self):
        return f"{self.shelf.name} — {self.product.name}: {self.quantity}"


class WipShelfStockMovement(models.Model):
    """Append-only audit ledger for WipShelfStock changes — WIP-side twin of ShelfStockMovement."""

    class Reason(models.TextChoices):
        RECIPE_BREAKDOWN_PUTAWAY  = "recipe_breakdown_putaway",  "Recipe Breakdown Put-Away"
        CUTTING_ISSUE_CONSUMPTION = "cutting_issue_consumption", "Cutting Issue Consumption"
        CUTTING_BREAKDOWN_PUTAWAY = "cutting_breakdown_putaway", "Cutting Breakdown Put-Away"
        PACKING_ISSUE_CONSUMPTION = "packing_issue_consumption", "Packing Issue Consumption"
        LOST_CONSUMPTION         = "lost_consumption",         "Lost Inventory Consumption"
        LOST_FOUND_PUTAWAY       = "lost_found_putaway",       "Lost Inventory Found Put-Away"

    shelf      = models.ForeignKey("purchases.Shelf", on_delete=models.PROTECT, related_name="wip_movements")
    product    = models.ForeignKey("production.WipProduct", on_delete=models.PROTECT, related_name="shelf_movements")
    delta      = models.DecimalField(max_digits=14, decimal_places=4, help_text="Positive = added to shelf, negative = removed from shelf.")
    reason     = models.CharField(max_length=30, choices=Reason.choices, db_index=True)
    reference  = models.CharField(max_length=30, blank=True, default="", help_text="e.g. REC-2026-0001")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="wip_shelf_stock_movements",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table            = "production_wipshelfstockmovement"
        verbose_name        = "WIP Shelf Stock Movement"
        verbose_name_plural = "WIP Shelf Stock Movements"
        ordering            = ["-created_at"]

    def __str__(self):
        return f"{self.shelf.name} — {self.product.name}: {self.delta:+} ({self.reason})"


# Products with 0 < quantity <= LOW_STOCK_THRESHOLD count as "low stock";
# quantity <= 0 counts as "out of stock". Single source of truth for the
# stats singleton, the breakdown selectors, and the backfill command.
LOW_STOCK_THRESHOLD = 5


class InventoryStatsFlow(models.Model):
    """
    Single live record — O(1) inventory stats for the Inventory page cards
    (total products, total stock, low stock, out of stock). Counts cover
    inventory rows of non-deleted products only, matching what the
    inventory list shows. Kept in sync by services.sync_inventory() (the
    ONLY quantity writer, used by purchases AND billing) and
    services.delete_product(); rebuilt from live data by
    backfill_inventory_stats. total_stock is maintained via the actual
    APPLIED delta (post floor-at-0 clamping), never the raw requested
    delta, so it can never drift from a live re-sum.
    """
    total_products     = models.PositiveIntegerField(default=0)
    total_stock        = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    low_stock_count    = models.PositiveIntegerField(default=0)
    out_of_stock_count = models.PositiveIntegerField(default=0)
    last_updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table             = "purchases_inventorystatsflow"
        verbose_name        = "Inventory Stats Flow"
        verbose_name_plural = "Inventory Stats Flow"

    def __str__(self):
        return (
            f"InventoryStatsFlow — total {self.total_products}, stock {self.total_stock}, "
            f"low {self.low_stock_count}, out {self.out_of_stock_count}"
        )

    @classmethod
    def get_instance(cls):
        instance, _ = cls.objects.get_or_create(pk=1)
        return instance


# ---------------------------------------------------------------------------
# FG Inventory (2026-09) — brand new tables, not a relocation (FgProduct
# itself is new too). Same split as RM/WIP: the catalog (production.FgProduct)
# stays with the producing app, the inventory tracking lives here.
# ---------------------------------------------------------------------------

class FgInventory(models.Model):
    product         = models.OneToOneField("production.FgProduct", on_delete=models.PROTECT, related_name="inventory")
    quantity        = models.DecimalField(max_digits=14, decimal_places=4, default=0, db_index=True)
    last_updated_at = models.DateTimeField(auto_now=True)
    last_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="fg_inventory_updates",
    )

    class Meta:
        verbose_name        = "FG Inventory"
        verbose_name_plural = "FG Inventories"
        ordering            = ["product__name"]

    def __str__(self):
        return f"{self.product.name} — qty: {self.quantity}"


class FgShelfStock(models.Model):
    """Live physical quantity of one FG product on one shelf — FG-side twin of ShelfStock/WipShelfStock."""
    shelf           = models.ForeignKey("purchases.Shelf", on_delete=models.PROTECT, related_name="fg_stock_rows")
    product         = models.ForeignKey("production.FgProduct", on_delete=models.PROTECT, related_name="shelf_stock_rows")
    quantity        = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    last_updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "FG Shelf Stock"
        verbose_name_plural = "FG Shelf Stock"
        unique_together     = [("shelf", "product")]

    def __str__(self):
        return f"{self.shelf.name} — {self.product.name}: {self.quantity}"


class FgShelfStockMovement(models.Model):
    """Append-only audit ledger for FgShelfStock changes — FG-side twin of ShelfStockMovement/WipShelfStockMovement."""

    class Reason(models.TextChoices):
        PACKING_OUTPUT_PUTAWAY = "packing_output_putaway", "Packing Output Put-Away"
        LOST_CONSUMPTION       = "lost_consumption",       "Lost Inventory Consumption"
        LOST_FOUND_PUTAWAY     = "lost_found_putaway",     "Lost Inventory Found Put-Away"

    shelf      = models.ForeignKey("purchases.Shelf", on_delete=models.PROTECT, related_name="fg_movements")
    product    = models.ForeignKey("production.FgProduct", on_delete=models.PROTECT, related_name="shelf_movements")
    delta      = models.DecimalField(max_digits=14, decimal_places=4, help_text="Positive = added to shelf, negative = removed from shelf.")
    reason     = models.CharField(max_length=30, choices=Reason.choices, db_index=True)
    reference  = models.CharField(max_length=30, blank=True, default="", help_text="e.g. PAK-2026-0001")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="fg_shelf_stock_movements",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name        = "FG Shelf Stock Movement"
        verbose_name_plural = "FG Shelf Stock Movements"
        ordering            = ["-created_at"]

    def __str__(self):
        return f"{self.shelf.name} — {self.product.name}: {self.delta:+} ({self.reason})"


class FgInventoryStatsFlow(models.Model):
    """FG-side twin of InventoryStatsFlow/WipInventoryStatsFlow — kept in sync by services.sync_fg_inventory()."""
    total_products     = models.PositiveIntegerField(default=0)
    total_stock        = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    low_stock_count    = models.PositiveIntegerField(default=0)
    out_of_stock_count = models.PositiveIntegerField(default=0)
    last_updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "FG Inventory Stats Flow"
        verbose_name_plural = "FG Inventory Stats Flow"

    def __str__(self):
        return (
            f"FgInventoryStatsFlow — total {self.total_products}, stock {self.total_stock}, "
            f"low {self.low_stock_count}, out {self.out_of_stock_count}"
        )

    @classmethod
    def get_instance(cls):
        instance, _ = cls.objects.get_or_create(pk=1)
        return instance


class ProductRegistryEntry(models.Model):
    """
    One row per product across all 3 stages (RM/WIP/FG) — a pure identity
    index (name/code/category), NOT a stock ledger. `quantity` is fetched
    live at read time via a join to the matching stage's own Inventory
    table (see selectors.get_all_registry_products), never denormalized
    here — that avoids a 4th place needing to stay in sync on every stock
    movement (sync_inventory/sync_wip_inventory/sync_fg_inventory are
    already the single writers for their own tables; adding a registry
    write to every one of those would be a new drift vector for no real
    benefit, since name/code/category never change after creation anyway).

    Written ONCE, at product-creation time (see
    purchases.services.get_or_create_product_variant,
    production.services.rewinding/cutting's WipProduct creation,
    production.services.packing's FgProduct creation) — never updated
    afterward, matching this project's existing "these fields are frozen
    once set" convention for all three product catalogs.

    Built to replace get_combined_inventory_rows' old Python-side merge of
    3 separately-fetched, separately-sorted querysets (O(catalog size) on
    every request) with a single indexed, offset-paginated query (O(page
    size)) — see docs/manufacturing-costing-notes.md and
    instructions/multi-inventory-expansion.md's already-planned "future
    registry model" note, which anticipated this exact shape.
    """
    class Type(models.TextChoices):
        RAW_MATERIAL   = "raw_material",   "Raw Material"
        WIP_CORE       = "wip_core",       "WIP Core"
        WIP_PIECE      = "wip_piece",      "WIP Piece"
        FINISHED_GOODS = "finished_goods", "Finished Goods"

    type        = models.CharField(max_length=20, choices=Type.choices, db_index=True)
    # Exactly one of these three is set per row (enforced by the
    # CheckConstraint below) — mirrors the design note's "real FK columns,
    # one nullable FK per stage's product table" over a generic
    # source_model/source_id string pair, for referential integrity.
    rm_product  = models.OneToOneField("purchases.Product", null=True, blank=True, on_delete=models.CASCADE, related_name="registry_entry")
    wip_product = models.OneToOneField("production.WipProduct", null=True, blank=True, on_delete=models.CASCADE, related_name="registry_entry")
    fg_product  = models.OneToOneField("production.FgProduct", null=True, blank=True, on_delete=models.CASCADE, related_name="registry_entry")
    name        = models.CharField(max_length=255, db_index=True)
    code        = models.CharField(max_length=30, null=True, blank=True)
    category    = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name        = "Product Registry Entry"
        verbose_name_plural = "Product Registry Entries"
        indexes = [
            models.Index(fields=["type", "name"]),
        ]
        constraints = [
            models.CheckConstraint(
                name="registry_exactly_one_product_fk",
                condition=(
                    (models.Q(rm_product__isnull=False) & models.Q(wip_product__isnull=True) & models.Q(fg_product__isnull=True)) |
                    (models.Q(rm_product__isnull=True) & models.Q(wip_product__isnull=False) & models.Q(fg_product__isnull=True)) |
                    (models.Q(rm_product__isnull=True) & models.Q(wip_product__isnull=True) & models.Q(fg_product__isnull=False))
                ),
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.type})"


class WipInventoryStatsFlow(models.Model):
    """
    WIP-side twin of InventoryStatsFlow — same O(1)-stats role, same shape
    (total products, total stock, low stock, out of stock — WIP gets the
    same LOW_STOCK_THRESHOLD treatment as RM, per project decision), kept
    in sync by services.sync_wip_inventory(). A real new table (not a
    state-only relocation like WipInventory/WipShelfStock/
    WipShelfStockMovement) — WIP never had stats tracking before.
    """
    total_products     = models.PositiveIntegerField(default=0)
    total_stock        = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    low_stock_count    = models.PositiveIntegerField(default=0)
    out_of_stock_count = models.PositiveIntegerField(default=0)
    last_updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "WIP Inventory Stats Flow"
        verbose_name_plural = "WIP Inventory Stats Flow"

    def __str__(self):
        return (
            f"WipInventoryStatsFlow — total {self.total_products}, stock {self.total_stock}, "
            f"low {self.low_stock_count}, out {self.out_of_stock_count}"
        )

    @classmethod
    def get_instance(cls):
        instance, _ = cls.objects.get_or_create(pk=1)
        return instance
