from django.conf import settings
from django.db import models


class ProductRate(models.Model):
    """
    One row per product — always holds the current active selling price.
    Never deleted. Updated in-place whenever the price changes.
    Every update is logged to ProductRateHistory automatically via service.

    rm_product/fg_product (exactly one set, enforced below) replaced the
    single `product` FK (2026-09) — this app now prices Finished Goods as
    the normal path, plus RM Cartons-family variants specifically (see
    purchases.selectors.is_cartons_product). Every other RM product is no
    longer priceable through this app going forward, but any pre-existing
    RM rate row is untouched. Both FKs keep `related_name="rate"` — on two
    different target models (purchases.Product / production.FgProduct) this
    doesn't collide, and it means billing's `product.rate.selling_price`
    price lookup needs no branching by product type at all.
    """

    rm_product = models.OneToOneField(
        "purchases.Product",
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name="rate",
    )
    fg_product = models.OneToOneField(
        "production.FgProduct",
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name="rate",
    )
    selling_price = models.DecimalField(max_digits=14, decimal_places=4)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="rate_updates",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="rate_creates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Product Rate"
        verbose_name_plural = "Product Rates"
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                name="productrate_exactly_one_product",
                condition=(
                    (models.Q(rm_product__isnull=False) & models.Q(fg_product__isnull=True)) |
                    (models.Q(rm_product__isnull=True) & models.Q(fg_product__isnull=False))
                ),
            ),
        ]

    def __str__(self):
        return f"{self.product.name} — {self.selling_price}"

    @property
    def product(self):
        return self.fg_product or self.rm_product


class UnpricedProduct(models.Model):
    """
    One row per product that has no ProductRate yet — the "needs a price
    set" queue. Kept in sync explicitly (never a live join over the full
    product catalog): purchases.services.create_product() adds a row here
    for a new Cartons-family variant (rates.selectors filters the queue view
    to Cartons + FG — see below), production.services.finish_packing_recipe
    adds one for a newly get-or-created FgProduct, and
    rates.services.create_rate() removes it once a price is set. Mirrors the
    cash_flow.CashMovement pattern — a materialized set instead of a
    recomputed-on-every-read join.

    rm_product/fg_product (exactly one set) replaced the single `product`
    FK (2026-09) — same reasoning as ProductRate.
    """

    rm_product = models.OneToOneField(
        "purchases.Product",
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="unpriced_entry",
    )
    fg_product = models.OneToOneField(
        "production.FgProduct",
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="unpriced_entry",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Unpriced Product"
        verbose_name_plural = "Unpriced Products"
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                name="unpricedproduct_exactly_one_product",
                condition=(
                    (models.Q(rm_product__isnull=False) & models.Q(fg_product__isnull=True)) |
                    (models.Q(rm_product__isnull=True) & models.Q(fg_product__isnull=False))
                ),
            ),
        ]

    def __str__(self):
        return f"{self.product.name} — no price set"

    @property
    def product(self):
        return self.fg_product or self.rm_product


class ProductRateHistory(models.Model):
    """
    Append-only audit log. A new row is inserted on every price change.
    Never updated or deleted — pure historical record.
    Billing uses this to snapshot the price at the time of invoice creation.

    rm_product/fg_product (exactly one set) replaced the single `product`
    FK (2026-09) — same reasoning as ProductRate.
    """

    rm_product = models.ForeignKey(
        "purchases.Product",
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name="rate_history",
    )
    fg_product = models.ForeignKey(
        "production.FgProduct",
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name="rate_history",
    )
    selling_price = models.DecimalField(max_digits=14, decimal_places=4)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="rate_history_changes",
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Optional reason for price change.",
    )

    class Meta:
        verbose_name = "Product Rate History"
        verbose_name_plural = "Product Rate Histories"
        ordering = ["-changed_at"]
        constraints = [
            models.CheckConstraint(
                name="productratehistory_exactly_one_product",
                condition=(
                    (models.Q(rm_product__isnull=False) & models.Q(fg_product__isnull=True)) |
                    (models.Q(rm_product__isnull=True) & models.Q(fg_product__isnull=False))
                ),
            ),
        ]
        indexes = [
            # Speeds up billing lookup: "price of product X on date Y"
            models.Index(fields=["rm_product", "-changed_at"], name="idx_rate_hist_rm_prod_date"),
            models.Index(fields=["fg_product", "-changed_at"], name="idx_rate_hist_fg_prod_date"),
        ]

    def __str__(self):
        return f"{self.product.name} — {self.selling_price} @ {self.changed_at:%Y-%m-%d %H:%M}"

    @property
    def product(self):
        return self.fg_product or self.rm_product