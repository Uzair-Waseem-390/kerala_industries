from django.conf import settings
from django.db import models


# ---------------------------------------------------------------------------
# Shared managers / audit mixin — mirrors purchases.models exactly (each app
# in this project defines its own copy rather than sharing a base app).
# ---------------------------------------------------------------------------

class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class AllObjectsManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset()


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
# WIP attribute lookups (Rewinding stage). Unlike RM's lookups (manually
# pre-populated by an admin before purchase), these rows are auto-created via
# get_or_create the first time a recipe's breakdown derives a given value —
# full CRUD is still exposed (admin-only) for visibility/cleanup.
# ---------------------------------------------------------------------------

class RewoundCoreBinding(AuditMixin):
    """Jumbo name/binding text copied from the issued Jumbo at breakdown time (e.g. "binding 210")."""
    value = models.CharField(max_length=255, unique=True)

    class Meta:
        verbose_name        = "Rewound Core Binding"
        verbose_name_plural = "Rewound Core Bindings"
        ordering            = ["value"]

    def __str__(self):
        return self.value


class RewoundCoreYard(AuditMixin):
    """Per-core wound yard length entered on a breakdown item (e.g. 100, 200, 10)."""
    value = models.DecimalField(max_digits=14, decimal_places=4, unique=True)

    class Meta:
        verbose_name        = "Rewound Core Yard"
        verbose_name_plural = "Rewound Core Yards"
        ordering            = ["value"]

    def __str__(self):
        return str(self.value)


class RewoundCoreLengthMm(AuditMixin):
    """RM core length converted inches -> mm (see production.utils.inches_to_mm)."""
    value = models.DecimalField(max_digits=14, decimal_places=4, unique=True)

    class Meta:
        verbose_name        = "Rewound Core Length (mm)"
        verbose_name_plural = "Rewound Core Lengths (mm)"
        ordering            = ["value"]

    def __str__(self):
        return str(self.value)


# ---------------------------------------------------------------------------
# WIP Product + Inventory (Rewound Cores) — structurally separate from RM's
# purchases.Product / inventory.Inventory, per
# instructions/multi-inventory-expansion.md. `family` reuses the existing
# purchases.Family "WIP" row (a stage tag, not a shared Product/Inventory
# table) — always set to that row for every WipProduct.
# ---------------------------------------------------------------------------

class WipProduct(AuditMixin):
    class Stage(models.TextChoices):
        REWINDING = "rewinding", "Rewinding"
        CUTTING   = "cutting",   "Cutting"

    name        = models.CharField(max_length=255)
    family      = models.ForeignKey("purchases.Family", on_delete=models.PROTECT, related_name="wip_products")
    binding     = models.ForeignKey(RewoundCoreBinding, on_delete=models.PROTECT, related_name="wip_products")
    yard        = models.ForeignKey(RewoundCoreYard, on_delete=models.PROTECT, related_name="wip_products")
    length_mm   = models.ForeignKey(RewoundCoreLengthMm, on_delete=models.PROTECT, related_name="wip_products")
    # Which stage's breakdown produced this row — a whole Rewound Core
    # ("rewinding") vs. an already-Cut Piece ("cutting"). Both are shaped
    # identically (binding+yard+length_mm), so nothing else distinguishes
    # them; Cutting's issuable-core search filters to stage="rewinding" so
    # an already-cut piece can never be re-issued as if it were a whole
    # core. Defaults to "rewinding" for backward compatibility with rows
    # created before this field existed.
    stage       = models.CharField(max_length=20, choices=Stage.choices, default=Stage.REWINDING, db_index=True)
    # Deterministic fingerprint of (binding, yard, length_mm) — same
    # mechanism as purchases.Product.variant_key: a real DB-enforced
    # uniqueness guarantee so an identical combo across recipes reuses this
    # row (quantity accumulates) instead of creating a duplicate.
    variant_key = models.CharField(max_length=500, unique=True, editable=False)

    class Meta:
        verbose_name        = "WIP Product"
        verbose_name_plural = "WIP Products"
        ordering            = ["name"]

    def __str__(self):
        return self.name


# WipInventory / WipShelfStock / WipShelfStockMovement moved to the
# inventory app (2026-09) — "operate everything WIP-inventory-related from
# the inventory app" per project decision. See inventory/models.py; Meta.db_table
# there is pinned to these same original table names, so this is a state-only
# move (production/migrations/..._remove_wip_models_state_only.py), not a
# real schema change. WipProduct (the catalog) stays here.


# ---------------------------------------------------------------------------
# Recipe (Rewinding) — header + issued RM materials + FIFO consumption
# ledger + breakdown output items.
# ---------------------------------------------------------------------------

class Recipe(AuditMixin):
    class Status(models.TextChoices):
        UNDER_PROCESSING = "under_processing", "Under Processing"
        FINISHED         = "finished",         "Finished"

    class RecipeType(models.TextChoices):
        REWINDING = "rewinding", "Rewinding"
        CUTTING   = "cutting",   "Cutting"
        # PACKING recipe type lands here once that stage is built.

    recipe_number = models.CharField(max_length=30, unique=True, editable=False)
    recipe_type   = models.CharField(max_length=20, choices=RecipeType.choices, default=RecipeType.REWINDING, db_index=True)
    # Overrides AuditMixin.created_at to add an index — get_all_recipes()
    # (and Recipe.Meta.ordering below) sorts by -created_at on every list
    # request, same reasoning as PurchaseOrder.created_at.
    created_at    = models.DateTimeField(auto_now_add=True, db_index=True)
    name          = models.CharField(max_length=255)
    # Not required at creation — mandatory only at finish_recipe time (see
    # production.services), so the user can fill it in any time while the
    # recipe is under_processing.
    description   = models.TextField(blank=True, default="")
    status        = models.CharField(max_length=20, choices=Status.choices, default=Status.UNDER_PROCESSING, db_index=True)
    # Blended per-unit cost across the whole recipe's output — computed and
    # frozen once, at finish_recipe (see production.services). Null while
    # under_processing.
    cost_per_unit = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True, editable=False)
    # Cutting only — total issued length not converted into output pieces
    # (waste_length_mm) and that length's cost, both frozen at
    # finish_cutting_recipe. Null for Rewinding recipes and while
    # under_processing.
    waste_length_mm = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True, editable=False)
    waste_cost      = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True, editable=False)
    finished_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="finished_recipes",
    )
    # Indexed: it's the sort/lock-order key for Cutting's WIP FIFO
    # (get_available_wip_batches_for_fifo orders by recipe__finished_at,
    # return_fifo locks batches in that same order) — same reasoning as
    # PurchaseOrder.confirmed_at being indexed for RM's FIFO ordering.
    finished_at   = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name        = "Recipe"
        verbose_name_plural = "Recipes"
        ordering            = ["-created_at"]

    def __str__(self):
        return f"{self.recipe_number} — {self.name}"


class RecipeIssuedMaterial(models.Model):
    """
    Exactly one Jumbo row + one Cores row per recipe (DB-enforced via
    unique_together). `quantity` is the currently-issued amount — this row
    IS the "recipe inventory" the client described: RM stock pulled out of
    RM but not yet transformed into WIP, visible only on this recipe.
    """
    class MaterialKind(models.TextChoices):
        JUMBO = "jumbo", "Jumbo"
        CORES = "cores", "Cores"

    recipe   = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="issued_materials")
    kind     = models.CharField(max_length=10, choices=MaterialKind.choices)
    product  = models.ForeignKey("purchases.Product", on_delete=models.PROTECT, related_name="recipe_issuances")
    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0)

    class Meta:
        verbose_name        = "Recipe Issued Material"
        verbose_name_plural = "Recipe Issued Materials"
        unique_together     = [("recipe", "kind")]

    def __str__(self):
        return f"{self.recipe.recipe_number} — {self.kind}: {self.quantity}"


class RecipeMaterialShelfDraw(models.Model):
    """
    Which shelf(s) an issue/increase pulled from, or a decrease returned to
    — purely a display/audit record ("Drawn From" on the recipe detail
    page). Deliberately NOT tied to a specific RecipeMaterialConsumption row
    (FIFO-batch selection and shelf selection are independent choices —
    one issue call can span multiple batches AND multiple shelves with no
    natural 1:1 mapping between them), so this tracks shelf activity at the
    issued-material level instead.
    """
    class Direction(models.TextChoices):
        DRAW   = "draw",   "Drawn From"
        RETURN = "return", "Returned To"

    issued_material = models.ForeignKey(RecipeIssuedMaterial, on_delete=models.CASCADE, related_name="shelf_draws")
    shelf           = models.ForeignKey("purchases.Shelf", on_delete=models.PROTECT, related_name="recipe_material_draws")
    direction       = models.CharField(max_length=10, choices=Direction.choices)
    quantity        = models.DecimalField(max_digits=14, decimal_places=4)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Recipe Material Shelf Draw"
        verbose_name_plural = "Recipe Material Shelf Draws"
        ordering            = ["created_at"]

    def __str__(self):
        return f"{self.issued_material} {self.direction} {self.shelf.name}: {self.quantity}"


class RecipeMaterialConsumption(models.Model):
    """
    FIFO ledger — which RM PurchaseItem batch(es) an issued-material row
    actually drew from, and how much at what cost. Mirrors billing.FIFOLedger.
    Needed for (a) the recipe's blended cost, (b) knowing exactly what to
    restore to RM (remaining_quantity + Inventory) when the user decreases
    an issuance — most-recent-first.
    """
    issued_material = models.ForeignKey(RecipeIssuedMaterial, on_delete=models.CASCADE, related_name="consumptions")
    purchase_item   = models.ForeignKey("purchases.PurchaseItem", on_delete=models.PROTECT, related_name="recipe_consumptions")
    quantity        = models.DecimalField(max_digits=14, decimal_places=4)
    unit_cost       = models.DecimalField(max_digits=14, decimal_places=4)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Recipe Material Consumption"
        verbose_name_plural = "Recipe Material Consumptions"
        ordering            = ["created_at"]

    def __str__(self):
        return f"{self.issued_material} <- {self.purchase_item}: {self.quantity}"


class RecipeBreakdownItem(AuditMixin):
    """
    One output line of a recipe: a WIP product + quantity produced.
    unit_cost_snapshot is filled once, at finish_recipe. remaining_quantity
    mirrors PurchaseItem.remaining_quantity's role — this row is WIP's own
    FIFO cost layer, so a later Cutting-stage recipe can consume WIP the
    same way Rewinding consumes RM.
    """
    recipe             = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="breakdown_items")
    wip_product        = models.ForeignKey(WipProduct, on_delete=models.PROTECT, related_name="breakdown_items")
    quantity           = models.DecimalField(max_digits=14, decimal_places=4)
    remaining_quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    unit_cost_snapshot = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)

    class Meta:
        verbose_name        = "Recipe Breakdown Item"
        verbose_name_plural = "Recipe Breakdown Items"
        ordering            = ["created_at"]

    def __str__(self):
        return f"{self.recipe.recipe_number} — {self.wip_product.name}: {self.quantity}"


class RecipeBreakdownItemShelfAllocation(models.Model):
    """
    Which shelf(s) a breakdown item's produced quantity was put away to —
    same role as purchases.PurchaseItemShelfAllocation plays for a purchase
    line, and shown the same way on the recipe detail page.
    """
    breakdown_item = models.ForeignKey(RecipeBreakdownItem, on_delete=models.CASCADE, related_name="shelf_allocations")
    shelf          = models.ForeignKey("purchases.Shelf", on_delete=models.PROTECT, related_name="recipe_breakdown_allocations")
    quantity       = models.DecimalField(max_digits=14, decimal_places=4)

    class Meta:
        verbose_name        = "Recipe Breakdown Item Shelf Allocation"
        verbose_name_plural = "Recipe Breakdown Item Shelf Allocations"
        unique_together     = [("breakdown_item", "shelf")]

    def __str__(self):
        return f"{self.breakdown_item} → {self.shelf.name}: {self.quantity}"


# ---------------------------------------------------------------------------
# Recipe (Cutting) — header is the same shared `Recipe` (recipe_type=
# "cutting"). Issued material/consumption/breakdown are separate, parallel
# models (not reused from the Rewinding ones above) because they point at a
# structurally different source: a WIP `RecipeBreakdownItem` FIFO batch
# instead of an RM `PurchaseItem` batch — mirrors this project's existing
# "RM/WIP/FG are structurally separate" principle one level down (Rewinding
# output vs. Cutting input), rather than bolting nullable alternate FKs onto
# the Rewinding models.
# ---------------------------------------------------------------------------

class CuttingIssuedMaterial(models.Model):
    """
    Exactly one row per Cutting recipe (unlike Rewinding's Jumbo+Cores pair)
    — Cutting only ever issues one WIP core product. `quantity` is pieces of
    the whole core issued; this row IS the "recipe inventory" for Cutting,
    same role RecipeIssuedMaterial plays for Rewinding.
    """
    recipe      = models.OneToOneField(Recipe, on_delete=models.CASCADE, related_name="cutting_issued_material")
    wip_product = models.ForeignKey(WipProduct, on_delete=models.PROTECT, related_name="cutting_issuances")
    quantity    = models.DecimalField(max_digits=14, decimal_places=4, default=0)

    class Meta:
        verbose_name        = "Cutting Issued Material"
        verbose_name_plural = "Cutting Issued Materials"

    def __str__(self):
        return f"{self.recipe.recipe_number} — {self.wip_product.name}: {self.quantity}"


class CuttingMaterialShelfDraw(models.Model):
    """Audit-only shelf activity for a Cutting issuance — mirrors RecipeMaterialShelfDraw."""
    class Direction(models.TextChoices):
        DRAW   = "draw",   "Drawn From"
        RETURN = "return", "Returned To"

    issued_material = models.ForeignKey(CuttingIssuedMaterial, on_delete=models.CASCADE, related_name="shelf_draws")
    shelf           = models.ForeignKey("purchases.Shelf", on_delete=models.PROTECT, related_name="cutting_material_draws")
    direction       = models.CharField(max_length=10, choices=Direction.choices)
    quantity        = models.DecimalField(max_digits=14, decimal_places=4)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Cutting Material Shelf Draw"
        verbose_name_plural = "Cutting Material Shelf Draws"
        ordering            = ["created_at"]

    def __str__(self):
        return f"{self.issued_material} {self.direction} {self.shelf.name}: {self.quantity}"


class CuttingMaterialConsumption(models.Model):
    """
    FIFO ledger — which WIP `RecipeBreakdownItem` batch(es) (i.e. which
    finished Rewinding batch) a Cutting issuance actually drew from, and how
    much at what cost. Mirrors RecipeMaterialConsumption exactly, one level
    up the chain (WIP batch instead of RM batch).
    """
    issued_material = models.ForeignKey(CuttingIssuedMaterial, on_delete=models.CASCADE, related_name="consumptions")
    wip_batch       = models.ForeignKey(RecipeBreakdownItem, on_delete=models.PROTECT, related_name="cutting_consumptions")
    quantity        = models.DecimalField(max_digits=14, decimal_places=4)
    unit_cost       = models.DecimalField(max_digits=14, decimal_places=4)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Cutting Material Consumption"
        verbose_name_plural = "Cutting Material Consumptions"
        ordering            = ["created_at"]

    def __str__(self):
        return f"{self.issued_material} <- {self.wip_batch}: {self.quantity}"


class CuttingBreakdownItem(AuditMixin):
    """
    One output line of a Cutting recipe: a cut-piece WIP product + the cut
    length (mm) + quantity of pieces at that length. unit_cost_before_waste
    and unit_cost_snapshot (final, after waste is spread across all pieces)
    are both filled once, at finish_cutting_recipe — see
    instructions/architecture.md's waste-absorption rule.
    """
    recipe                  = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="cutting_breakdown_items")
    wip_product             = models.ForeignKey(WipProduct, on_delete=models.PROTECT, related_name="cutting_breakdown_items")
    length_mm               = models.DecimalField(max_digits=14, decimal_places=4)
    quantity                = models.DecimalField(max_digits=14, decimal_places=4)
    remaining_quantity      = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    unit_cost_before_waste  = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    unit_cost_snapshot      = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)

    class Meta:
        verbose_name        = "Cutting Breakdown Item"
        verbose_name_plural = "Cutting Breakdown Items"
        ordering            = ["created_at"]

    def __str__(self):
        return f"{self.recipe.recipe_number} — {self.wip_product.name}: {self.quantity}"


class CuttingBreakdownItemShelfAllocation(models.Model):
    """Which shelf(s) a Cutting breakdown item's produced quantity was put away to — mirrors RecipeBreakdownItemShelfAllocation."""
    breakdown_item = models.ForeignKey(CuttingBreakdownItem, on_delete=models.CASCADE, related_name="shelf_allocations")
    shelf          = models.ForeignKey("purchases.Shelf", on_delete=models.PROTECT, related_name="cutting_breakdown_allocations")
    quantity       = models.DecimalField(max_digits=14, decimal_places=4)

    class Meta:
        verbose_name        = "Cutting Breakdown Item Shelf Allocation"
        verbose_name_plural = "Cutting Breakdown Item Shelf Allocations"
        unique_together     = [("breakdown_item", "shelf")]

    def __str__(self):
        return f"{self.breakdown_item} → {self.shelf.name}: {self.quantity}"
