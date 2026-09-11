from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import models


class Employee(models.Model):
    """
    A production laborer, for Direct Labor costing. Only what the DL rate
    formula needs — no payroll/HR concept here, just enough to derive a
    per-hour rate: rate/hour = monthly_salary ÷ (avg_hours_per_day ×
    working_days_per_month). `rate_per_hour` is stored (recomputed and
    re-saved on every edit), never recomputed on read — O(1), matches every
    other rate/stat field in this codebase.

    Rates are "set-once-until-changed" — editing an employee's rate only
    affects recipes/batches created AFTER the change; nothing reads back
    through to anything already created (recipe-level integration is a
    later phase, not built yet — this field exists for that future use,
    stored now so it's ready).
    """
    name                    = models.CharField(max_length=255)
    monthly_salary          = models.DecimalField(max_digits=14, decimal_places=4)
    avg_hours_per_day       = models.DecimalField(max_digits=6, decimal_places=2)
    working_days_per_month  = models.DecimalField(max_digits=6, decimal_places=2)
    rate_per_hour           = models.DecimalField(max_digits=14, decimal_places=4, default=0, editable=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="mfg_employees_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="mfg_employees_updated",
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="mfg_employees_deleted",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    objects = models.Manager()

    class Meta:
        verbose_name        = "Employee"
        verbose_name_plural  = "Employees"
        ordering             = ["name"]

    def __str__(self):
        return self.name

    def compute_rate_per_hour(self) -> Decimal:
        monthly_hours = self.avg_hours_per_day * self.working_days_per_month
        if monthly_hours <= 0:
            return Decimal("0")
        return (self.monthly_salary / monthly_hours).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


class Machine(models.Model):
    """
    A production machine, for Factory Overhead costing. Category is a plain
    choices field — exactly 3 fixed values, no lookup table/seed command
    needed (per project decision, 2026-09).

    `rate_per_hour` is the machine's OWN repair/maintenance cost PLUS its
    proportional share of the shared Rent+Electricity pool (see
    services.recompute_machine_rate for the exact formula) — one blended
    rate per machine, stored, O(1) read. Recomputed whenever this machine's
    own inputs change, OR whenever FactoryOverheadSetting's rent/electricity
    changes (which cascades across every machine).
    """
    class Category(models.TextChoices):
        REWINDING = "rewinding", "Rewinding"
        CUTTING   = "cutting",   "Cutting"
        PACKING   = "packing",   "Packing"

    name                    = models.CharField(max_length=255)
    category                = models.CharField(max_length=20, choices=Category.choices, db_index=True)
    avg_hours_per_day       = models.DecimalField(max_digits=6, decimal_places=2)
    working_days_per_month  = models.DecimalField(max_digits=6, decimal_places=2)
    monthly_repair_cost     = models.DecimalField(max_digits=14, decimal_places=4)
    rate_per_hour           = models.DecimalField(max_digits=14, decimal_places=4, default=0, editable=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="mfg_machines_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="mfg_machines_updated",
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="mfg_machines_deleted",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    objects = models.Manager()

    class Meta:
        verbose_name        = "Machine"
        verbose_name_plural  = "Machines"
        ordering             = ["name"]

    def __str__(self):
        return self.name

    def monthly_hours(self) -> Decimal:
        return self.avg_hours_per_day * self.working_days_per_month


class FactoryOverheadSetting(models.Model):
    """
    Singleton (same get_instance() pattern as CashFlow/InventoryStatsFlow) —
    the two shared, factory-wide overhead figures (Rent, Electricity) that
    get allocated across every machine proportional to its own hours. Both
    default to 0; a value of 0 is a valid, deliberate "not entered" state,
    not a missing-data error. Changing either triggers a recompute of every
    Machine.rate_per_hour (see services.update_factory_overhead_setting).
    """
    rent_amount        = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    electricity_amount = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="mfg_foh_settings_updated",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Factory Overhead Setting"
        verbose_name_plural  = "Factory Overhead Setting"

    def __str__(self):
        return f"FactoryOverheadSetting — rent {self.rent_amount}, electricity {self.electricity_amount}"

    @classmethod
    def get_instance(cls):
        instance, _ = cls.objects.get_or_create(pk=1)
        return instance


class PayableEntity(models.Model):
    """
    Page 4's registry row — one per Employee, one per Machine, plus exactly
    one fixed Rent row and one fixed Electricity row (singleton per type,
    get_or_create'd once). Never created directly by a user — auto-created
    the instant an Employee/Machine is created (see services), or lazily
    get_or_create'd for the two fixed types.

    Deliberately NOT the source of truth for money — `Payment` rows are.
    `overall_total_paid`/`overall_payment_count` are incrementally
    maintained O(1) counters (same Flow-singleton discipline as everywhere
    else in this codebase) used to derive an all-time monthly average
    without ever summing Payment rows live. "Last month" / "last 3 months
    average" come from PayableEntityMonthlySnapshot instead (see that
    model) — this entity itself does not story per-period figures.
    """
    class Type(models.TextChoices):
        EMPLOYEE    = "employee",    "Employee"
        MACHINE     = "machine",     "Machine"
        RENT        = "rent",        "Rent"
        ELECTRICITY = "electricity", "Electricity"

    type     = models.CharField(max_length=20, choices=Type.choices, db_index=True)
    employee = models.OneToOneField(Employee, null=True, blank=True, on_delete=models.PROTECT, related_name="payable_entity")
    machine  = models.OneToOneField(Machine, null=True, blank=True, on_delete=models.PROTECT, related_name="payable_entity")

    overall_total_paid    = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    overall_payment_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="mfg_payable_entities_deleted",
    )
    deleted_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    objects = models.Manager()

    class Meta:
        verbose_name        = "Payable Entity"
        verbose_name_plural  = "Payable Entities"
        constraints = [
            models.CheckConstraint(
                name="payableentity_type_matches_source",
                condition=(
                    (models.Q(type="employee") & models.Q(employee__isnull=False) & models.Q(machine__isnull=True)) |
                    (models.Q(type="machine") & models.Q(employee__isnull=True) & models.Q(machine__isnull=False)) |
                    (models.Q(type__in=["rent", "electricity"]) & models.Q(employee__isnull=True) & models.Q(machine__isnull=True))
                ),
            ),
            models.UniqueConstraint(fields=["type"], condition=models.Q(type__in=["rent", "electricity"]), name="payableentity_singleton_rent_electricity"),
        ]

    def __str__(self):
        if self.employee_id:
            return f"Employee — {self.employee.name}"
        if self.machine_id:
            return f"Machine — {self.machine.name}"
        return self.get_type_display()

    @property
    def name(self) -> str:
        if self.employee_id:
            return self.employee.name
        if self.machine_id:
            return self.machine.name
        return self.get_type_display()

    @property
    def overall_average_monthly(self) -> Decimal:
        """
        All-time average, O(1) — overall_total_paid ÷ elapsed months since
        this entity was created (never less than 1), no Payment scan. This
        is a live arithmetic derivation off two already-stored counters,
        not a query — the O(1) guarantee is about avoiding a live SUM over
        Payment rows, not literally zero computation.
        """
        from django.utils import timezone
        today = timezone.localdate()
        created = timezone.localtime(self.created_at).date()
        elapsed_months = max(1, (today.year - created.year) * 12 + (today.month - created.month) + 1)
        if self.overall_total_paid <= 0:
            return Decimal("0")
        return (self.overall_total_paid / elapsed_months).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


class PayableEntityMonthlySnapshot(models.Model):
    """
    One frozen row per (entity, period) — created ONLY for closed months
    (never the current, still-open one), via the catch-up-on-read mechanism
    (mirrors assets.AssetFlow's marker-gated per-entity sweep — see
    ManufacturingCostsFlow). This is what makes "last month's expense" and
    "average of the last 3 months" O(1)/bounded reads instead of live
    aggregation over Payment rows — see architecture.md.
    """
    entity     = models.ForeignKey(PayableEntity, on_delete=models.CASCADE, related_name="monthly_snapshots")
    period     = models.CharField(max_length=7, db_index=True, help_text="YYYY-MM")
    total_paid = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Payable Entity Monthly Snapshot"
        verbose_name_plural  = "Payable Entity Monthly Snapshots"
        ordering             = ["-period"]
        constraints = [
            models.UniqueConstraint(fields=["entity", "period"], name="uniq_payable_entity_snapshot_period"),
        ]

    def __str__(self):
        return f"{self.entity} — {self.period}: {self.total_paid}"


class ManufacturingCostsFlow(models.Model):
    """
    Single live record — O(1) gate for the monthly snapshot catch-up, same
    role as assets.AssetFlow.depreciation_caught_up_through. Once this
    month has already been caught up, catch_up_manufacturing_costs_snapshots
    short-circuits without touching a single PayableEntity row.
    """
    snapshots_caught_up_through = models.CharField(max_length=7, null=True, blank=True, help_text="YYYY-MM")
    last_updated_at             = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Manufacturing Costs Flow"
        verbose_name_plural  = "Manufacturing Costs Flow"

    def __str__(self):
        return f"ManufacturingCostsFlow — caught up through {self.snapshots_caught_up_through}"

    @classmethod
    def get_instance(cls):
        instance, _ = cls.objects.get_or_create(pk=1)
        return instance


class ManufacturingCostsStats(models.Model):
    """
    Singleton — the Overview page's ENTIRE data source, same get_instance()
    discipline as every other Flow-style stats model in this codebase
    (CashFlow, InventoryStatsFlow, ...). Every field here is maintained
    incrementally at the exact write sites that change it (see services.py),
    never derived from a live Sum()/Count() at read time — one row, one
    query, genuinely O(1).

    total_estimated_monthly_dl  = Σ active employees' monthly_salary.
    total_estimated_monthly_foh = Σ active machines' monthly_repair_cost
                                   + FactoryOverheadSetting.rent_amount
                                   + FactoryOverheadSetting.electricity_amount.
    last_month_dl_paid/last_month_foh_paid are stamped once a month by
    catch_up_manufacturing_costs_snapshots (a bounded aggregate over
    PayableEntityMonthlySnapshot rows for the one just-closed period — NOT a
    live scan of Payment history), not touched anywhere else.

    this_month_dl_paid/this_month_foh_paid are a running total of the
    CURRENT (still-open) calendar month's real payments — incremented/
    decremented by F() at create_payment/delete_payment, O(1), never a live
    Sum() over Payment rows. A backdated payment recorded today for a PAST
    month does NOT touch these (only a payment whose OWN payment_date falls
    in the current calendar month does) — see
    services._ensure_this_month_counters_current. this_month_period tracks
    which YYYY-MM the running totals currently represent; whenever a write
    or a read notices the real calendar month has rolled over, both
    counters reset to 0 for the new month (same "tick on read/write, no
    cron" idiom as every other catch-up in this app). This is exactly the
    "record now, cost at month-end" real-time figure profits.services reads
    for its live (not-yet-finalized) current-month net profit.

    total_dl_foh_accrued (2026-09) is a SEPARATE, never-reset, all-time
    running total of every DL+FOH pool ever embedded into
    production.PackingOutputItem/CuttingBreakdownItem/RecipeBreakdownItem's
    full_unit_cost_snapshot (see production.services._shared.compute_labor_overhead_pool
    and its 3 call sites in production/services/{rewinding,cutting,packing}.py)
    — the ACCRUED side of manufacturing cost, independent of when/whether
    that labor was actually paid in cash. Paired with
    PayableEntity.overall_total_paid (already an all-time running total) via
    accounting.selectors.get_dl_foh_payable_balance() to give the Balance
    Sheet a real "Accrued Manufacturing Cost Payable" liability line — the
    missing double-entry counterpart to capitalizing DL+FOH into inventory
    value. See profits.selectors._compute_current_month_figures's docstring
    for why DL/FOH cash paid is no longer subtracted from net_profit
    directly (COGS-on-sale recognizes it instead) — this field is what
    reconciles the resulting gap on the Balance Sheet.
    """
    total_employees             = models.PositiveIntegerField(default=0)
    total_machines               = models.PositiveIntegerField(default=0)
    total_estimated_monthly_dl   = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    total_estimated_monthly_foh  = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    last_month_dl_paid           = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    last_month_foh_paid          = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    this_month_dl_paid           = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    this_month_foh_paid          = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    this_month_period            = models.CharField(max_length=7, null=True, blank=True, help_text="YYYY-MM")
    total_dl_foh_accrued         = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    last_updated_at              = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Manufacturing Costs Stats"
        verbose_name_plural  = "Manufacturing Costs Stats"

    def __str__(self):
        return "ManufacturingCostsStats"

    @classmethod
    def get_instance(cls):
        instance, _ = cls.objects.get_or_create(pk=1)
        return instance


class Payment(models.Model):
    """
    One real payment against a PayableEntity — the ONLY thing in this app
    that touches cash-in-hand (creating an Employee/Machine/adjusting
    FactoryOverheadSetting never does). Soft-deletable; deleting one is the
    ONLY operation that reverses cash — deleting a PayableEntity itself
    never touches any Payment or its cash effect (see services).

    reference_number is real and stored (unlike cash_flow.Expense's ad-hoc
    f"EXP-{id}") specifically so it's searchable — same next_reference/
    DocumentCounter mechanism purchases/billing already use for PO-2026-0001
    etc., counter_key="MFG".
    """
    reference_number = models.CharField(max_length=30, unique=True, editable=False)
    entity           = models.ForeignKey(PayableEntity, on_delete=models.PROTECT, related_name="payments")
    amount           = models.DecimalField(max_digits=18, decimal_places=4)
    payment_date     = models.DateField(db_index=True)
    note             = models.TextField(blank=True, default="")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="mfg_payments_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="mfg_payments_updated",
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="mfg_payments_deleted",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    objects = models.Manager()

    class Meta:
        verbose_name        = "Payment"
        verbose_name_plural  = "Payments"
        ordering             = ["-payment_date", "-created_at"]

    def __str__(self):
        return f"{self.reference_number} — {self.entity}: {self.amount}"
