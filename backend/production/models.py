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
    # Sequential auto-generated code (WIP-2026-0001), assigned at creation —
    # see production.services._shared.next_wip_product_code. Every row has
    # one — backfill_wip_product_codes filled in rows created before this
    # field existed.
    code        = models.CharField(max_length=30, unique=True, editable=False)
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


class FgProduct(AuditMixin):
    """
    Finished Goods catalog row — one per packed piece identity. Deliberately
    reuses WIP's own binding/yard/length_mm lookups (not a fresh FG-scoped
    set) because Packing doesn't transform the product — per project
    decision, a packed piece is the *same* identity as the WIP piece it came
    from ("no name change, only moves from WIP to Finished Good"), so a
    second parallel set of attribute lookups would fight that, not serve it.
    Still a structurally separate catalog/table from WipProduct itself
    (RM/WIP/FG separation principle), just pointed at the same lookup rows.
    """
    name        = models.CharField(max_length=255)
    code        = models.CharField(max_length=30, unique=True, editable=False)
    binding     = models.ForeignKey(RewoundCoreBinding, on_delete=models.PROTECT, related_name="fg_products")
    yard        = models.ForeignKey(RewoundCoreYard, on_delete=models.PROTECT, related_name="fg_products")
    length_mm   = models.ForeignKey(RewoundCoreLengthMm, on_delete=models.PROTECT, related_name="fg_products")
    # Same fingerprint mechanism as WipProduct.variant_key — get-or-create
    # by (binding, yard, length_mm) so packing the same piece identity again
    # reuses this row instead of creating a duplicate.
    variant_key = models.CharField(max_length=500, unique=True, editable=False)

    class Meta:
        verbose_name        = "FG Product"
        verbose_name_plural = "FG Products"
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
        PACKING   = "packing",   "Packing"

    recipe_number = models.CharField(max_length=30, unique=True, editable=False)
    recipe_type   = models.CharField(max_length=20, choices=RecipeType.choices, default=RecipeType.REWINDING, db_index=True)
    # True only for the synthetic "Opening Stock" recipes data_entry's WIP/FG
    # bootstrap creates (production.services.opening_stock) — a real,
    # FIFO-consumable batch-bearing Recipe under the hood, but excluded from
    # get_all_recipes() by default so it never shows up in the Recipes list
    # as if real manufacturing work happened. Same shape/purpose as
    # purchases.PurchaseOrder.is_data_entry / billing.Invoice.is_data_entry.
    is_data_entry = models.BooleanField(default=False, db_index=True)
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
    # frozen once, at finish_recipe (see production.services). Material cost
    # only (no Direct Labor / Factory Overhead) — see full_cost_per_unit
    # below for the cost incl. DL+FOH. Null while under_processing.
    cost_per_unit = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True, editable=False)
    # cost_per_unit + this recipe's own DL+FOH pool spread flat across the
    # output — the "Full Manufacturing Cost" (material + labor + overhead),
    # NOT the same thing as COGS (COGS is only recognized when a unit is
    # actually sold — see docs/cogs-gross-profit-engine-notes.md). This is
    # the cost basis that flows into the next production stage / FG
    # inventory. Frozen once, at finish. Null while under_processing.
    full_cost_per_unit = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True, editable=False)
    # Hours + minutes this batch took — entered by the user before finishing
    # (see validate_labor_and_machines in services/_shared.py). Both default
    # 0; at least one must be non-zero to finish. Combined as
    # time_hours + time_minutes/60 for the DL/FOH pool calculation.
    time_hours   = models.PositiveIntegerField(default=0)
    time_minutes = models.PositiveIntegerField(default=0)
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


class RecipeLabor(models.Model):
    """
    One employee assigned to a recipe's batch. rate_per_hour_snapshot is
    locked at the moment the employee is added — mirrors this project's
    "snapshot at lock-in" rule, since manufacturing_costs.Employee.rate_per_hour
    can change later and this recipe's cost must not silently drift with it.
    """
    recipe                = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="labor_entries")
    employee               = models.ForeignKey("manufacturing_costs.Employee", on_delete=models.PROTECT, related_name="recipe_labor_entries")
    rate_per_hour_snapshot = models.DecimalField(max_digits=14, decimal_places=4)
    created_at              = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Recipe Labor"
        verbose_name_plural = "Recipe Labor"
        unique_together     = [("recipe", "employee")]
        ordering            = ["created_at"]

    def __str__(self):
        return f"{self.recipe.recipe_number} — {self.employee.name}"


class RecipeMachine(models.Model):
    """
    One machine assigned to a recipe's batch — restricted at the service
    layer to machines whose category matches the recipe's own recipe_type.
    rate_per_hour_snapshot is locked at the moment the machine is added,
    same reasoning as RecipeLabor.
    """
    recipe                 = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="machine_entries")
    machine                 = models.ForeignKey("manufacturing_costs.Machine", on_delete=models.PROTECT, related_name="recipe_machine_entries")
    rate_per_hour_snapshot  = models.DecimalField(max_digits=14, decimal_places=4)
    created_at               = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Recipe Machine"
        verbose_name_plural = "Recipe Machines"
        unique_together     = [("recipe", "machine")]
        ordering            = ["created_at"]

    def __str__(self):
        return f"{self.recipe.recipe_number} — {self.machine.name}"


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
    # unit_cost_snapshot + this recipe's DL+FOH pool share — the Full
    # Manufacturing Cost. This is what flows into Cutting as its material
    # cost (see production.services.cutting._core_unit_cost_fn), not
    # unit_cost_snapshot. Frozen at finish_recipe alongside it.
    full_unit_cost_snapshot = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)

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
    # unit_cost_snapshot (labeled "After Waste" in the UI) + this recipe's
    # DL+FOH pool share — the Full Manufacturing Cost. This is what flows
    # into Packing as the issued piece's material cost (see
    # production.services.packing._piece_unit_cost_fn), not
    # unit_cost_snapshot. Frozen at finish_cutting_recipe alongside it.
    full_unit_cost_snapshot = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)

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


# ---------------------------------------------------------------------------
# Recipe (Packing) — header is the same shared `Recipe` (recipe_type=
# "packing"). Two independent inputs per recipe: a Cut Piece (WIP) and a
# Packing Material (RM, kg) — mirrors Rewinding's Jumbo+Cores pair
# structurally, but the two inputs point at different source tables (WIP vs
# RM) so they can't share one polymorphic model the way Jumbo/Cores do.
# No breakdown stage — output quantity == issued piece quantity, 1:1, no
# split (see instructions/architecture.md and the 2026-09 design
# discussion: packing doesn't transform the product, so there's nothing to
# allocate by length/waste the way Cutting does).
# ---------------------------------------------------------------------------

class PackingIssuedPiece(models.Model):
    """Exactly one Cut Piece (WIP, stage=cutting) product issued per Packing recipe."""
    recipe      = models.OneToOneField(Recipe, on_delete=models.CASCADE, related_name="packing_issued_piece")
    wip_product = models.ForeignKey(WipProduct, on_delete=models.PROTECT, related_name="packing_issuances")
    quantity    = models.DecimalField(max_digits=14, decimal_places=4, default=0)

    class Meta:
        verbose_name        = "Packing Issued Piece"
        verbose_name_plural = "Packing Issued Pieces"

    def __str__(self):
        return f"{self.recipe.recipe_number} — {self.wip_product.name}: {self.quantity}"


class PackingPieceShelfDraw(models.Model):
    """Audit-only shelf activity for a Packing piece issuance — mirrors CuttingMaterialShelfDraw."""
    class Direction(models.TextChoices):
        DRAW   = "draw",   "Drawn From"
        RETURN = "return", "Returned To"

    issued_piece = models.ForeignKey(PackingIssuedPiece, on_delete=models.CASCADE, related_name="shelf_draws")
    shelf        = models.ForeignKey("purchases.Shelf", on_delete=models.PROTECT, related_name="packing_piece_draws")
    direction    = models.CharField(max_length=10, choices=Direction.choices)
    quantity     = models.DecimalField(max_digits=14, decimal_places=4)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Packing Piece Shelf Draw"
        verbose_name_plural = "Packing Piece Shelf Draws"
        ordering            = ["created_at"]

    def __str__(self):
        return f"{self.issued_piece} {self.direction} {self.shelf.name}: {self.quantity}"


class PackingPieceConsumption(models.Model):
    """
    FIFO ledger — which Cutting `CuttingBreakdownItem` batch(es) a Packing
    piece issuance drew from, and how much at what cost. Mirrors
    CuttingMaterialConsumption exactly, one level up the chain.
    """
    # Named `issued_material` (not `issued_piece`) so this model satisfies
    # the generic contract services/_shared.py's draw_fifo/return_fifo
    # helpers assume across every FIFO consumption model in this app
    # (RecipeMaterialConsumption/CuttingMaterialConsumption both use this
    # same field name) — those helpers hardcode the kwarg name.
    issued_material = models.ForeignKey(PackingIssuedPiece, on_delete=models.CASCADE, related_name="consumptions")
    piece_batch     = models.ForeignKey(CuttingBreakdownItem, on_delete=models.PROTECT, related_name="packing_consumptions")
    quantity        = models.DecimalField(max_digits=14, decimal_places=4)
    unit_cost       = models.DecimalField(max_digits=14, decimal_places=4)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Packing Piece Consumption"
        verbose_name_plural = "Packing Piece Consumptions"
        ordering            = ["created_at"]

    def __str__(self):
        return f"{self.issued_material} <- {self.piece_batch}: {self.quantity}"


class PackingIssuedMaterial(models.Model):
    """Exactly one RM packing material (kg) issued per Packing recipe — mirrors RecipeIssuedMaterial's role, one material instead of a Jumbo+Cores pair."""
    recipe   = models.OneToOneField(Recipe, on_delete=models.CASCADE, related_name="packing_issued_material")
    product  = models.ForeignKey("purchases.Product", on_delete=models.PROTECT, related_name="packing_issuances")
    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0)

    class Meta:
        verbose_name        = "Packing Issued Material"
        verbose_name_plural = "Packing Issued Materials"

    def __str__(self):
        return f"{self.recipe.recipe_number} — {self.product.name}: {self.quantity}"


class PackingMaterialShelfDraw(models.Model):
    """Audit-only shelf activity for a Packing RM material issuance — mirrors RecipeMaterialShelfDraw."""
    class Direction(models.TextChoices):
        DRAW   = "draw",   "Drawn From"
        RETURN = "return", "Returned To"

    issued_material = models.ForeignKey(PackingIssuedMaterial, on_delete=models.CASCADE, related_name="shelf_draws")
    shelf           = models.ForeignKey("purchases.Shelf", on_delete=models.PROTECT, related_name="packing_material_draws")
    direction       = models.CharField(max_length=10, choices=Direction.choices)
    quantity        = models.DecimalField(max_digits=14, decimal_places=4)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Packing Material Shelf Draw"
        verbose_name_plural = "Packing Material Shelf Draws"
        ordering            = ["created_at"]

    def __str__(self):
        return f"{self.issued_material} {self.direction} {self.shelf.name}: {self.quantity}"


class PackingMaterialConsumption(models.Model):
    """FIFO ledger — which RM `PurchaseItem` batch(es) a Packing material issuance drew from. Mirrors RecipeMaterialConsumption."""
    issued_material = models.ForeignKey(PackingIssuedMaterial, on_delete=models.CASCADE, related_name="consumptions")
    purchase_item   = models.ForeignKey("purchases.PurchaseItem", on_delete=models.PROTECT, related_name="packing_consumptions")
    quantity        = models.DecimalField(max_digits=14, decimal_places=4)
    unit_cost       = models.DecimalField(max_digits=14, decimal_places=4)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Packing Material Consumption"
        verbose_name_plural = "Packing Material Consumptions"
        ordering            = ["created_at"]

    def __str__(self):
        return f"{self.issued_material} <- {self.purchase_item}: {self.quantity}"


class PackingOutputItem(AuditMixin):
    """
    The single output row of a finished Packing recipe: the matching
    FgProduct + quantity (== issued piece quantity, 1:1, no split) +
    unit_cost_snapshot (piece's own final cost + packing cost spread evenly
    — see finish_packing_recipe). remaining_quantity mirrors
    CuttingBreakdownItem's role — FG's own FIFO cost layer, for a future
    sale path once billing integrates with FG (open question, see
    docs/manufacturing-costing-notes.md).
    """
    recipe             = models.OneToOneField(Recipe, on_delete=models.CASCADE, related_name="packing_output_item")
    fg_product         = models.ForeignKey(FgProduct, on_delete=models.PROTECT, related_name="packing_output_items")
    quantity           = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    remaining_quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    unit_cost_snapshot = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    # unit_cost_snapshot (labeled "Material Cost" in the UI — piece cost +
    # packing material cost) + this recipe's DL+FOH pool share — the Full
    # Manufacturing Cost of the FG unit. This is the cost basis that becomes
    # COGS when the unit is later sold (see docs/cogs-gross-profit-engine-notes.md).
    # Frozen at finish_packing_recipe alongside it.
    full_unit_cost_snapshot = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)

    class Meta:
        verbose_name        = "Packing Output Item"
        verbose_name_plural = "Packing Output Items"

    def __str__(self):
        return f"{self.recipe.recipe_number} — {self.fg_product.name}: {self.quantity}"


class PackingOutputShelfAllocation(models.Model):
    """Which shelf(s) a Packing output's produced quantity was put away to — mirrors CuttingBreakdownItemShelfAllocation."""
    output_item = models.ForeignKey(PackingOutputItem, on_delete=models.CASCADE, related_name="shelf_allocations")
    shelf       = models.ForeignKey("purchases.Shelf", on_delete=models.PROTECT, related_name="packing_output_allocations")
    quantity    = models.DecimalField(max_digits=14, decimal_places=4)

    class Meta:
        verbose_name        = "Packing Output Shelf Allocation"
        verbose_name_plural = "Packing Output Shelf Allocations"
        unique_together     = [("output_item", "shelf")]

    def __str__(self):
        return f"{self.output_item} → {self.shelf.name}: {self.quantity}"
