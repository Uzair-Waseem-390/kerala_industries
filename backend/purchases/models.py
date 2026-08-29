from decimal import Decimal
from django.conf import settings
from django.db import models

from .utils import calculate_total_price

# The 4 fixed family-anchor products' codes (seeded by seed_fixed_products,
# never re-created) — single source of truth so nothing else hardcodes
# these strings. Every attribute-bearing variant traces back to one of
# these via Product.base_product.
JUMBO_PRODUCT_CODE   = "PRO-1000"
CORES_PRODUCT_CODE   = "PRO-1001"
PACKING_PRODUCT_CODE = "PRO-1002"
CARTONS_PRODUCT_CODE = "PRO-1003"


# ---------------------------------------------------------------------------
# Shared managers
# ---------------------------------------------------------------------------

class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class AllObjectsManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset()


# ---------------------------------------------------------------------------
# Audit mixin — full trail + soft delete on every model
# ---------------------------------------------------------------------------

class AuditMixin(models.Model):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="%(class)s_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="%(class)s_updated",
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="%(class)s_deleted",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    objects     = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# Fixed-product attribute lookups (Jumbo/Cores/Packing/Cartons)
# ---------------------------------------------------------------------------
# Category (a flat product-catalog classification) was removed — Product is
# capped at exactly 4 fixed rows now, so a general-purpose category no
# longer serves a purpose; these 6 lookups are its replacement.
# Standalone lookup tables — NOT a FK on Product. Product is capped at
# exactly 4 fixed rows (seeded by seed_fixed_products, never created via
# API); these are simple, user-manageable value lists that future
# production/recipe records will reference to tag/filter their own rows
# (e.g. "this batch's core output was 1248mm length, 210 mic thickness").
# `value` is unique=True — a real unique B-tree index, exact-match lookups
# are O(log n)/effectively O(1), no trigram/GIN index needed since these
# are a controlled dropdown list, not free-text search targets.

class JumboName(AuditMixin):
    value = models.CharField(max_length=255, unique=True)

    class Meta:
        verbose_name        = "Jumbo Name"
        verbose_name_plural = "Jumbo Names"
        ordering            = ["value"]

    def __str__(self):
        return self.value


class CoreName(AuditMixin):
    value = models.CharField(max_length=255, unique=True)

    class Meta:
        verbose_name        = "Core Name"
        verbose_name_plural = "Core Names"
        ordering            = ["value"]

    def __str__(self):
        return self.value


class CoreLength(AuditMixin):
    value = models.CharField(max_length=255, unique=True)

    class Meta:
        verbose_name        = "Core Length"
        verbose_name_plural = "Core Lengths"
        ordering            = ["value"]

    def __str__(self):
        return self.value


class CoreThickness(AuditMixin):
    value = models.CharField(max_length=255, unique=True)

    class Meta:
        verbose_name        = "Core Thickness"
        verbose_name_plural = "Core Thicknesses"
        ordering            = ["value"]

    def __str__(self):
        return self.value


class PackingSize(AuditMixin):
    value = models.CharField(max_length=255, unique=True)

    class Meta:
        verbose_name        = "Packing Size"
        verbose_name_plural = "Packing Sizes"
        ordering            = ["value"]

    def __str__(self):
        return self.value


class CartonSize(AuditMixin):
    value = models.CharField(max_length=255, unique=True)

    class Meta:
        verbose_name        = "Carton Size"
        verbose_name_plural = "Carton Sizes"
        ordering            = ["value"]

    def __str__(self):
        return self.value


class Shelf(AuditMixin):
    name        = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, default="")

    class Meta:
        verbose_name        = "Shelf"
        verbose_name_plural = "Shelves"
        ordering            = ["name"]

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Supplier
# ---------------------------------------------------------------------------

class Supplier(AuditMixin):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name        = "Supplier"
        verbose_name_plural = "Suppliers"
        ordering            = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


# ---------------------------------------------------------------------------
# Family — fixed/seeded, mirrors Product: exactly 3 rows (Raw Material, WIP,
# Finished Goods — the inventory stage from client_requirements.md), no
# create/update/delete API. All 4 current Product rows are tagged
# "Raw Material" today; WIP/Finished Goods get their own separate product +
# inventory models later (per instructions/multi-inventory-expansion.md —
# not this field), but the field exists now so cross-stage reporting has
# somewhere to read "which stage" from without waiting on that build.
# ---------------------------------------------------------------------------

class Family(AuditMixin):
    name = models.CharField(max_length=255, unique=True)

    class Meta:
        verbose_name        = "Family"
        verbose_name_plural = "Families"
        ordering            = ["name"]

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------

class Product(AuditMixin):
    name   = models.CharField(max_length=255)
    code   = models.CharField(max_length=100, unique=True)
    family = models.ForeignKey(Family, on_delete=models.PROTECT, related_name="products")

    # Self-FK to one of the 4 canonical family-anchor rows (Jumbo/Cores/
    # Packing/Cartons — the only rows ever created via create_product()).
    # Null on the anchors themselves; every attribute-bearing variant points
    # back to which anchor "line" it belongs to. Needed because Family alone
    # (Raw Material/WIP/Finished Goods) doesn't disambiguate Jumbo from
    # Cores — all 4 anchors share family="Raw Material" today.
    base_product = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="variants",
    )

    # Attribute-based variant selection — only the field(s) relevant to a
    # row's base product are ever set; the rest stay null. A different
    # attribute combination is a different trackable inventory line (a
    # different Product row), not the same row with a different label — per
    # the client's explicit instruction. These rows are never created
    # directly by a user; only purchases.services.get_or_create_product_variant()
    # creates them, as a side effect of recording a purchase.
    jumbo_name      = models.ForeignKey(JumboName, on_delete=models.PROTECT, null=True, blank=True, related_name="products")
    core_name       = models.ForeignKey(CoreName, on_delete=models.PROTECT, null=True, blank=True, related_name="products")
    core_length     = models.ForeignKey(CoreLength, on_delete=models.PROTECT, null=True, blank=True, related_name="products")
    core_thickness  = models.ForeignKey(CoreThickness, on_delete=models.PROTECT, null=True, blank=True, related_name="products")
    packing_size    = models.ForeignKey(PackingSize, on_delete=models.PROTECT, null=True, blank=True, related_name="products")
    carton_size     = models.ForeignKey(CartonSize, on_delete=models.PROTECT, null=True, blank=True, related_name="products")

    # Deterministic fingerprint, computed by create_product()/
    # get_or_create_product_variant() before every create — a real,
    # DB-enforced uniqueness guarantee. For an anchor row: derived from its
    # own `code` (already unique). For a variant: derived from
    # (base_product + every attribute FK above). A plain unique_together
    # across the attribute columns would NOT reliably catch duplicate
    # variants — Postgres/SQLite treat every NULL as distinct for
    # uniqueness purposes, so two rows sharing one populated attribute but
    # NULL on the rest would never collide under a plain composite
    # constraint.
    variant_key = models.CharField(max_length=500, unique=True, editable=False)

    class Meta:
        verbose_name        = "Product"
        verbose_name_plural = "Products"
        ordering            = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


# ---------------------------------------------------------------------------
# Purchase Order (header) — renamed from Purchase
# ---------------------------------------------------------------------------

class PurchaseOrder(AuditMixin):
    """
    Header of a purchase. Mirrors billing.Invoice.
    Draft → no inventory/debt effect.
    Confirmed → inventory increases, supplier debt auto-created.
    """

    class Status(models.TextChoices):
        DRAFT     = "draft",     "Draft"
        CONFIRMED = "confirmed", "Confirmed"

    class PaymentStatus(models.TextChoices):
        UNPAID  = "unpaid",  "Unpaid"
        PARTIAL = "partial", "Partial"
        PAID    = "paid",    "Paid"

    class PaymentType(models.TextChoices):
        ADVANCE        = "advance",        "Advance Payment"
        AFTER_DELIVERY = "after_delivery", "Payment After Delivery"

    order_number = models.CharField(max_length=30, unique=True, editable=False)
    supplier     = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchase_orders")
    # Overrides AuditMixin.created_at to add an index — every order list view
    # sorts by -created_at and filters by date range, so without this the DB
    # re-sorts the whole table on each request. Same pattern as
    # LostInventoryRecord.created_at.
    created_at   = models.DateTimeField(auto_now_add=True, db_index=True)
    is_data_entry = models.BooleanField(
        default=False, db_index=True,
        help_text="True for bootstrap opening-balance / opening-stock orders. Hidden from normal list views.",
    )
    status       = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True)
    description  = models.TextField(blank=True, default="", help_text="Optional notes about this purchase order.")
    payment_type = models.CharField(
        max_length=20, choices=PaymentType.choices,
        default=PaymentType.AFTER_DELIVERY,
        help_text="Advance payment or payment after delivery.",
    )
    advance_amount = models.DecimalField(
        max_digits=18, decimal_places=4, default=0,
        help_text=(
            "Amount paid in advance (only when payment_type=advance). "
            "Immediately deducted from cash_in_hand on draft creation. "
            "Capped at net_payable on confirmation."
        ),
    )

    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="confirmed_purchase_orders",
    )
    confirmed_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # Totals — computed and stored on confirmation
    gross_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    gst_total    = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    wht_total    = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    net_payable  = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    # Supplier payable tracking — updated on every payment / return
    payable_outstanding = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    total_paid          = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    payment_status      = models.CharField(
        max_length=10, choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID, db_index=True,
    )

    class Meta:
        verbose_name        = "Purchase Order"
        verbose_name_plural = "Purchase Orders"
        ordering            = ["-created_at"]

    def __str__(self):
        return self.order_number


# ---------------------------------------------------------------------------
# Purchase Item (line item) — renamed from Purchase
# ---------------------------------------------------------------------------

class PurchaseItem(AuditMixin):
    """
    One line item inside a PurchaseOrder.
    remaining_quantity tracks FIFO consumption from billing.
    All financial fields auto-calculated on save.
    """

    order      = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="items")
    product    = models.ForeignKey(Product,       on_delete=models.PROTECT, related_name="purchase_items")
    quantity   = models.DecimalField(max_digits=14, decimal_places=4)
    unit_price = models.DecimalField(max_digits=14, decimal_places=4)
    gst        = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                     help_text="GST percentage e.g. 18.5 means 18.5%")
    wht        = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                     help_text="WHT percentage e.g. 1.5 means 1.5%")
    description = models.TextField(blank=True, default="", help_text="Optional description for this line item.")

    # Auto-calculated — never entered by user
    gross_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0, editable=False)
    gst_amount   = models.DecimalField(max_digits=18, decimal_places=4, default=0, editable=False)
    wht_amount   = models.DecimalField(max_digits=18, decimal_places=4, default=0, editable=False)
    total_price  = models.DecimalField(max_digits=18, decimal_places=4, default=0, editable=False)

    # FIFO tracking — set on confirmation, consumed by billing
    remaining_quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0)

    # Tracks how much of this line has been returned to supplier
    returned_quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0)

    # Jumbo/Packing purchase intake — only populated for those two families'
    # specialized "punch a purchase" forms (create_jumbo_purchase/
    # create_packing_purchase in services.py). Null for every other item.
    # total_cost (Jumbo) = rate_per_kg × weight_kg + freight_cost.
    weight_kg   = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    rate_per_kg = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    freight_cost = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True, default=0)

    # Jumbo only. expected_length_m is what's printed on the jumbo roll
    # (converted to yards via purchases.utils.meters_to_yards — that's what
    # `quantity` above is stored in). exact_length_m is set later, only if
    # the supervisor measures the roll and finds the printed length wrong —
    # see purchases.services.correct_jumbo_exact_length. Null until then.
    expected_length_m = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    exact_length_m    = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)

    class Meta:
        verbose_name        = "Purchase Item"
        verbose_name_plural = "Purchase Items"
        unique_together     = [("order", "product")]
        ordering            = ["id"]

    @property
    def allocated_quantity(self):
        # Sums the in-memory prefetch cache when the caller prefetched
        # shelf_allocations (the normal list/detail path) — .aggregate()
        # would bypass that cache and re-query per item (N+1).
        return sum(a.quantity for a in self.shelf_allocations.all())

    def save(self, *args, **kwargs):
        result = calculate_total_price(
            quantity=self.quantity,
            unit_price=self.unit_price,
            gst=self.gst,
            wht=self.wht,
        )
        self.gross_amount = result["gross_amount"]
        self.gst_amount   = result["gst_amount"]
        self.wht_amount   = result["wht_amount"]
        self.total_price  = result["total_price"]
        # Set remaining_quantity on first creation only (confirmation sets it via service)
        super().save(*args, **kwargs)

    @property
    def returnable_quantity(self):
        # Bounded by remaining_quantity, not just quantity - returned_quantity
        # — you can only return to the supplier what's still physically in
        # stock. A unit already sold to a customer or lost isn't returnable
        # to the supplier just because it hasn't been "returned" before.
        return min(self.quantity - self.returned_quantity, self.remaining_quantity)

    def __str__(self):
        return f"{self.order.order_number} — {self.product.name}"


class PurchaseItemShelfAllocation(models.Model):
    """
    Draft put-away plan for one PurchaseItem: which shelf(s) the purchased
    quantity will land on once the order is confirmed. Purely planning state
    until confirm_purchase_order runs — nothing is applied to ShelfStock
    until then. confirm_purchase_order blocks unless every item's
    allocations sum exactly to its quantity. Any shelf is allowed (put-away).
    """
    purchase_item = models.ForeignKey(PurchaseItem, on_delete=models.CASCADE, related_name="shelf_allocations")
    shelf         = models.ForeignKey(Shelf, on_delete=models.PROTECT, related_name="purchase_item_allocations")
    quantity      = models.DecimalField(max_digits=14, decimal_places=4)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Purchase Item Shelf Allocation"
        verbose_name_plural = "Purchase Item Shelf Allocations"
        unique_together     = [("purchase_item", "shelf")]

    def __str__(self):
        return f"{self.purchase_item} → {self.shelf.name}: {self.quantity}"


# ---------------------------------------------------------------------------
# Purchase Return
# ---------------------------------------------------------------------------

class PurchaseReturn(AuditMixin):
    """
    Return of goods to supplier. Always a new record — previous PurchaseOrder untouched.
    Accepted only by admin/superuser.
    On acceptance:
        - Inventory decreases (FIFO reversal on remaining_quantity)
        - Supplier payable_outstanding decreases
    """

    class Status(models.TextChoices):
        PENDING  = "pending",  "Pending"
        ACCEPTED = "accepted", "Accepted"

    order            = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="returns")
    reference_number = models.CharField(max_length=30, unique=True, editable=False,
                        #    default="", blank=True,
                           help_text="Auto-generated e.g. RTN-2026-0001")
    status           = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    note             = models.TextField(blank=True, default="")
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="accepted_purchase_returns",
    )
    accepted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    # Overrides AuditMixin.created_at to add an index — the returns list sorts
    # by -created_at and filters by date range. Same pattern as PurchaseOrder.
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)

    # Totals — computed on acceptance
    total_return_gross  = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    total_return_gst    = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    total_return_wht    = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    total_return_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    class Meta:
        verbose_name        = "Purchase Return"
        verbose_name_plural = "Purchase Returns"
        ordering            = ["-created_at"]

    def __str__(self):
        return f"Return for {self.order.order_number}"


class PurchaseReturnItem(models.Model):
    """
    One line item per product being returned in a PurchaseReturn.
    GST and WHT are optional (default 0) on return items.
    """

    return_record  = models.ForeignKey(PurchaseReturn, on_delete=models.CASCADE, related_name="items")
    purchase_item  = models.ForeignKey(PurchaseItem,   on_delete=models.PROTECT, related_name="return_items")
    quantity       = models.DecimalField(max_digits=14, decimal_places=4)
    gst            = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                         help_text="GST on return (optional, default 0)")
    wht            = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                         help_text="WHT on return (optional, default 0)")

    # Snapshotted on acceptance from original purchase item
    unit_price   = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    gross_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    gst_amount   = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    wht_amount   = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    total_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    class Meta:
        verbose_name        = "Purchase Return Item"
        verbose_name_plural = "Purchase Return Items"
        unique_together     = [("return_record", "purchase_item")]

    def __str__(self):
        return f"{self.return_record} — {self.purchase_item.product.name} x {self.quantity}"

    @property
    def allocated_quantity(self):
        # Sums the in-memory prefetch cache when the caller prefetched
        # shelf_allocations (the normal list/detail path) — .aggregate()
        # would bypass that cache and re-query per item (N+1).
        return sum(a.quantity for a in self.shelf_allocations.all())


class PurchaseReturnItemShelfAllocation(models.Model):
    """
    Draft plan for which shelf(s) the returned-to-supplier quantity is
    physically pulled from. Consumption, not put-away — only shelves that
    currently hold stock of this product are valid choices (enforced by the
    selector that lists candidate shelves + the service-layer quantity
    check). accept_purchase_return blocks unless every item's allocations
    sum exactly to its quantity.
    """
    return_item = models.ForeignKey(PurchaseReturnItem, on_delete=models.CASCADE, related_name="shelf_allocations")
    shelf       = models.ForeignKey(Shelf, on_delete=models.PROTECT, related_name="purchase_return_item_allocations")
    quantity    = models.DecimalField(max_digits=14, decimal_places=4)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Purchase Return Item Shelf Allocation"
        verbose_name_plural = "Purchase Return Item Shelf Allocations"
        unique_together     = [("return_item", "shelf")]

    def __str__(self):
        return f"{self.return_item} ← {self.shelf.name}: {self.quantity}"


# ---------------------------------------------------------------------------
# Lost Inventory
# ---------------------------------------------------------------------------

class LostInventoryRecord(AuditMixin):
    """
    A batch event where one or more products are marked as lost from inventory
    (damaged, expired, stolen, misplaced, etc.). Takes effect immediately on
    creation — unlike PurchaseReturn there is no pending/accept step.

    On creation:
        - Cost per unit is snapshotted from FIFO purchase batches (same
          costing logic as billing._run_fifo).
        - Inventory decreases immediately.
    """

    reference_number = models.CharField(max_length=30, unique=True, editable=False,
                           help_text="Auto-generated e.g. LOSS-2026-0001")
    note = models.TextField(blank=True, default="", help_text="Optional overall note for this batch.")

    # Computed and stored on creation
    total_lost_amount = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    # Overrides AuditMixin.created_at to add an index — this is the field the
    # Lost Inventory report filters/orders by. PurchaseOrder and PurchaseReturn
    # carry the same override; AuditMixin's other users (Category, Shelf,
    # Supplier, Product, SupplierPayment) stay unindexed on purpose.
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name        = "Lost Inventory Record"
        verbose_name_plural = "Lost Inventory Records"
        ordering            = ["-created_at"]

    def __str__(self):
        return self.reference_number


class LostInventoryItem(models.Model):
    """
    One product lost within a LostInventoryRecord.
    unit_cost is the blended FIFO cost snapshotted at creation time — immutable.

    found_quantity tracks how much of this line has since been marked "found"
    (product turned up again) via mark_lost_inventory_found — supports partial
    recovery across multiple separate find events, mirroring the
    quantity/returned_quantity pattern already used on PurchaseItem/InvoiceItem.
    """

    record   = models.ForeignKey(LostInventoryRecord, on_delete=models.CASCADE, related_name="items")
    product  = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="lost_inventory_items")
    quantity = models.DecimalField(max_digits=14, decimal_places=4)
    reason   = models.CharField(max_length=255, blank=True, default="",
                   help_text="Optional reason e.g. damaged, expired, stolen, misplaced.")

    # Snapshotted from FIFO purchase batches at creation
    unit_cost  = models.DecimalField(max_digits=14, decimal_places=4, default=0, editable=False)
    total_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0, editable=False)

    # How much of this loss has been reversed via "mark as found"
    found_quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0)

    class Meta:
        verbose_name        = "Lost Inventory Item"
        verbose_name_plural = "Lost Inventory Items"
        unique_together     = [("record", "product")]

    @property
    def returnable_quantity(self):
        return self.quantity - self.found_quantity

    @property
    def recovered_amount(self):
        return self.unit_cost * self.found_quantity

    @property
    def net_amount(self):
        return self.total_cost - self.recovered_amount

    def __str__(self):
        return f"{self.record.reference_number} — {self.product.name} x {self.quantity}"


class LostInventoryRecovery(models.Model):
    """
    One row per "mark as found" action — the dated counterpart to
    LostInventoryItem.found_quantity (which is just a running counter with
    no timestamp). This is what lets the Monthly Profit report correctly
    attribute a recovery to the month it ACTUALLY happened in, instead of
    silently folding it into the month the original loss was recorded in
    (which breaks once that month is already finalized/frozen).

    recovered_amount is snapshotted at creation (unit_cost × quantity for
    that specific find event) — immutable, same "snapshot at lock-in"
    convention as everything else in this app.
    """
    lost_item        = models.ForeignKey(LostInventoryItem, on_delete=models.CASCADE, related_name="recoveries")
    quantity          = models.DecimalField(max_digits=14, decimal_places=4)
    recovered_amount  = models.DecimalField(max_digits=18, decimal_places=4, editable=False)
    recovered_at      = models.DateField(db_index=True)
    recovered_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="lost_inventory_recoveries",
    )
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Lost Inventory Recovery"
        verbose_name_plural = "Lost Inventory Recoveries"
        ordering            = ["-recovered_at", "-id"]

    def __str__(self):
        return f"{self.lost_item.product.name} — {self.quantity} recovered on {self.recovered_at}"


class LostInventoryFIFOConsumption(models.Model):
    """
    Records exactly which purchase batch(es) a LostInventoryItem's quantity
    was drawn from at the moment it was marked lost — mirrors billing.FIFOLedger.
    A single loss can span multiple batches (FIFO may need to pull from more
    than one PurchaseItem to cover the lost quantity), so this is one row per
    batch actually touched, not one row per LostInventoryItem.

    Enables mark_lost_inventory_found to restore the EXACT original batches
    instead of an approximation. restored_quantity tracks how much of THIS
    specific consumption has already been reversed (supports partial finds
    that only partially restore a given row before moving to the next).
    """

    lost_item     = models.ForeignKey(LostInventoryItem, on_delete=models.CASCADE, related_name="fifo_consumptions")
    purchase_item = models.ForeignKey(PurchaseItem, on_delete=models.PROTECT, related_name="lost_inventory_consumptions")
    quantity      = models.DecimalField(max_digits=14, decimal_places=4, help_text="Quantity originally drawn from this batch when marked lost.")
    unit_cost     = models.DecimalField(max_digits=14, decimal_places=4, help_text="Tax-inclusive unit cost of this batch at the time of loss.")
    restored_quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Lost Inventory FIFO Consumption"
        verbose_name_plural = "Lost Inventory FIFO Consumptions"
        ordering            = ["id"]

    @property
    def restorable_quantity(self):
        return self.quantity - self.restored_quantity

    def __str__(self):
        return f"{self.lost_item} ← {self.purchase_item} x {self.quantity}"


# ---------------------------------------------------------------------------
# Supplier Payment
# ---------------------------------------------------------------------------

class SupplierPayment(AuditMixin):
    """
    Payment made to a supplier against a PurchaseOrder.
    One order can have multiple partial payments over time.
    payment_type is stored for future use (no logic difference currently).
    """

    class Method(models.TextChoices):
        """
        Legacy label choices, kept for get_method_display()/backward
        compatibility. Since payment_methods.PaymentMethod (a real account,
        possibly user-created) replaced this as the actual source of truth,
        `method` can hold any account's name (lower-cased) or "multiple" for
        a split payment — values outside this list are still accepted at
        the ORM level (Django doesn't enforce `choices` on save()), they
        just fall back to showing the raw value via get_method_display().
        """
        CASH      = "cash",      "Cash"
        JAZZCASH  = "jazzcash",  "JazzCash"
        EASYPAISA = "easypaisa", "Easypaisa"
        BANK      = "bank",      "Bank Transfer"
        MULTIPLE  = "multiple",  "Multiple Methods"

    order            = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="payments")
    reference_number = models.CharField(max_length=30, unique=True, editable=False,
                        #    default="", blank=True,
                           help_text="Auto-generated e.g. SPY-2026-0001")
    amount           = models.DecimalField(max_digits=18, decimal_places=4)
    method           = models.CharField(
        max_length=100, choices=Method.choices,
        help_text="Derived display label — see payment_methods.PaymentAllocation for the real split.",
    )
    payment_date     = models.DateField(db_index=True)
    note             = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        verbose_name        = "Supplier Payment"
        verbose_name_plural = "Supplier Payments"
        ordering            = ["-payment_date"]

    def __str__(self):
        return f"{self.order.order_number} — {self.method} {self.amount}"


# ---------------------------------------------------------------------------
# Saved Purchase Order PDF
# ---------------------------------------------------------------------------

class SavedPurchaseOrderPDF(models.Model):
    """
    Tracks every PDF saved for a confirmed PurchaseOrder.
    Mirrors billing.SavedInvoicePDF — same pattern.
    """

    order      = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="saved_pdfs")
    file_name  = models.CharField(max_length=255)
    file_path  = models.CharField(max_length=500)
    saved_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="saved_purchase_pdfs",
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="deleted_purchase_pdfs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    objects     = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        verbose_name        = "Saved Purchase Order PDF"
        verbose_name_plural = "Saved Purchase Order PDFs"
        ordering            = ["-created_at"]

    def __str__(self):
        return f"{self.order.order_number} — {self.file_name}"


# ---------------------------------------------------------------------------
# Inventory, ShelfStock, ShelfStockMovement, ProductStockMovement,
# StockMovementFlow, InventoryStatsFlow, and LOW_STOCK_THRESHOLD moved to the
# `inventory` app (mechanical extraction — same tables, same behavior; see
# inventory/models.py and the paired SeparateDatabaseAndState migrations).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Document reference counters
# ---------------------------------------------------------------------------

class DocumentCounter(models.Model):
    """
    One row per document type per year holding the last sequence number used
    (PO-2026-#### / SPY / RTN / LOSS). Reference generation locks this row
    (select_for_update), increments, and formats — O(1) and race-safe, unlike
    the old "sort existing references as text" approach, which was O(N) per
    create, collided under concurrency, and broke permanently at sequence
    10000 (text sort puts '9999' after '10000'). Seeded lazily from the
    numeric max of existing references the first time a (doc_type, year)
    is used.
    """
    doc_type    = models.CharField(max_length=10)
    year        = models.PositiveIntegerField()
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name        = "Document Counter"
        verbose_name_plural = "Document Counters"
        unique_together     = [("doc_type", "year")]

    def __str__(self):
        return f"{self.doc_type}-{self.year} — last {self.last_number}"