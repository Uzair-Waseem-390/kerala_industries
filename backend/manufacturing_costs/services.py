from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from purchases.services import next_reference

from .models import (
    Employee, FactoryOverheadSetting, Machine, ManufacturingCostsFlow, ManufacturingCostsStats,
    PayableEntity, PayableEntityMonthlySnapshot, Payment,
)


def _next_payment_reference() -> str:
    return next_reference(counter_key="MFG", prefix_label="MFG", model=Payment, field="reference_number")


def _soft_delete(instance, user) -> None:
    instance.is_deleted = True
    instance.deleted_at = timezone.now()
    instance.deleted_by = user
    instance.save(update_fields=["is_deleted", "deleted_at", "deleted_by"])


# ---------------------------------------------------------------------------
# Employee
# ---------------------------------------------------------------------------

@transaction.atomic
def create_employee(*, name: str, monthly_salary: Decimal, avg_hours_per_day: Decimal, working_days_per_month: Decimal, user) -> Employee:
    from rest_framework.exceptions import ValidationError
    if not name or not name.strip():
        raise ValidationError({"name": "Name is required."})
    if monthly_salary <= 0:
        raise ValidationError({"monthly_salary": "Monthly salary must be greater than zero."})
    if avg_hours_per_day <= 0:
        raise ValidationError({"avg_hours_per_day": "Average hours per day must be greater than zero."})
    if working_days_per_month <= 0:
        raise ValidationError({"working_days_per_month": "Working days per month must be greater than zero."})

    employee = Employee(
        name=name.strip(), monthly_salary=monthly_salary,
        avg_hours_per_day=avg_hours_per_day, working_days_per_month=working_days_per_month,
        created_by=user, updated_by=user,
    )
    employee.rate_per_hour = employee.compute_rate_per_hour()
    employee.save()

    PayableEntity.objects.create(type=PayableEntity.Type.EMPLOYEE, employee=employee)

    ManufacturingCostsStats.get_instance()
    ManufacturingCostsStats.objects.filter(pk=1).update(
        total_employees=F("total_employees") + 1,
        total_estimated_monthly_dl=F("total_estimated_monthly_dl") + employee.monthly_salary,
    )
    return employee


@transaction.atomic
def update_employee(*, pk: int, user, **fields) -> Employee:
    from rest_framework.exceptions import ValidationError
    employee = Employee.objects.select_for_update().get(pk=pk, is_deleted=False)
    old_monthly_salary = employee.monthly_salary

    update_fields = ["updated_by", "updated_at"]
    for field in ("name", "monthly_salary", "avg_hours_per_day", "working_days_per_month"):
        if field in fields and fields[field] is not None:
            setattr(employee, field, fields[field])
            update_fields.append(field)

    if employee.monthly_salary <= 0:
        raise ValidationError({"monthly_salary": "Monthly salary must be greater than zero."})
    if employee.avg_hours_per_day <= 0:
        raise ValidationError({"avg_hours_per_day": "Average hours per day must be greater than zero."})
    if employee.working_days_per_month <= 0:
        raise ValidationError({"working_days_per_month": "Working days per month must be greater than zero."})

    employee.rate_per_hour = employee.compute_rate_per_hour()
    employee.updated_by = user
    update_fields.append("rate_per_hour")
    employee.save(update_fields=update_fields)

    salary_delta = employee.monthly_salary - old_monthly_salary
    if salary_delta != 0:
        ManufacturingCostsStats.objects.filter(pk=1).update(
            total_estimated_monthly_dl=F("total_estimated_monthly_dl") + salary_delta,
        )
    return employee


@transaction.atomic
def delete_employee(*, pk: int, user) -> None:
    employee = Employee.objects.get(pk=pk, is_deleted=False)
    _soft_delete(employee, user)

    ManufacturingCostsStats.objects.filter(pk=1).update(
        total_employees=F("total_employees") - 1,
        total_estimated_monthly_dl=F("total_estimated_monthly_dl") - employee.monthly_salary,
    )


# ---------------------------------------------------------------------------
# Machine + FOH rate computation
# ---------------------------------------------------------------------------

def _recompute_all_machine_rates(*, rent_amount: Decimal, electricity_amount: Decimal) -> None:
    """
    Runs whenever ANY input that affects a machine's blended rate changes —
    either FactoryOverheadSetting (rent/electricity) or a machine's own
    hours/repair-cost. O(N) in the number of machines — deliberately not a
    concern: N is bounded by real, physical factory equipment count (never
    "growing history"), same class of bounded-loop this codebase already
    accepts elsewhere (e.g. Cutting's FIFO batch walks).

    Formula (confirmed with the project owner):
        total_factory_hours = sum of every active machine's own monthly hours
        machine's share of (rent + electricity) = machine's own hours / total_factory_hours * (rent + electricity)
        machine's total FOH cost = machine's own repair cost + that share
        machine's rate/hour = machine's total FOH cost / machine's own hours
    """
    # select_for_update: two admins editing different machines (or one
    # editing a machine while another edits Rent/Electricity) at the same
    # moment could otherwise each read a pre-edit snapshot of
    # total_factory_hours/rent/electricity and bulk_update over each
    # other's result — a lost update on rate_per_hour. Locking the whole
    # set this function reads from closes that window; always called
    # inside the caller's own @transaction.atomic.
    machines = list(Machine.objects.select_for_update().filter(is_deleted=False))
    if not machines:
        return

    total_factory_hours = sum((m.monthly_hours() for m in machines), Decimal("0"))
    shared_pool = rent_amount + electricity_amount
    precision = Decimal("0.0001")

    for machine in machines:
        own_hours = machine.monthly_hours()
        if own_hours <= 0:
            machine.rate_per_hour = Decimal("0")
            continue
        share = (own_hours / total_factory_hours * shared_pool) if total_factory_hours > 0 else Decimal("0")
        total_foh_cost = machine.monthly_repair_cost + share
        machine.rate_per_hour = (total_foh_cost / own_hours).quantize(precision, rounding=ROUND_HALF_UP)

    Machine.objects.bulk_update(machines, ["rate_per_hour"])


@transaction.atomic
def create_machine(*, name: str, category: str, avg_hours_per_day: Decimal, working_days_per_month: Decimal, monthly_repair_cost: Decimal, user) -> Machine:
    from rest_framework.exceptions import ValidationError
    if not name or not name.strip():
        raise ValidationError({"name": "Name is required."})
    if category not in Machine.Category.values:
        raise ValidationError({"category": f"category must be one of {Machine.Category.values}."})
    if avg_hours_per_day <= 0:
        raise ValidationError({"avg_hours_per_day": "Average hours per day must be greater than zero."})
    if working_days_per_month <= 0:
        raise ValidationError({"working_days_per_month": "Working days per month must be greater than zero."})
    if monthly_repair_cost < 0:
        raise ValidationError({"monthly_repair_cost": "Monthly repair cost cannot be negative."})

    machine = Machine.objects.create(
        name=name.strip(), category=category,
        avg_hours_per_day=avg_hours_per_day, working_days_per_month=working_days_per_month,
        monthly_repair_cost=monthly_repair_cost,
        created_by=user, updated_by=user,
    )
    PayableEntity.objects.create(type=PayableEntity.Type.MACHINE, machine=machine)

    ManufacturingCostsStats.get_instance()
    ManufacturingCostsStats.objects.filter(pk=1).update(
        total_machines=F("total_machines") + 1,
        total_estimated_monthly_foh=F("total_estimated_monthly_foh") + machine.monthly_repair_cost,
    )

    setting = FactoryOverheadSetting.get_instance()
    _recompute_all_machine_rates(rent_amount=setting.rent_amount, electricity_amount=setting.electricity_amount)
    machine.refresh_from_db(fields=["rate_per_hour"])
    return machine


@transaction.atomic
def update_machine(*, pk: int, user, **fields) -> Machine:
    from rest_framework.exceptions import ValidationError
    machine = Machine.objects.select_for_update().get(pk=pk, is_deleted=False)
    old_monthly_repair_cost = machine.monthly_repair_cost

    update_fields = ["updated_by", "updated_at"]
    for field in ("name", "category", "avg_hours_per_day", "working_days_per_month", "monthly_repair_cost"):
        if field in fields and fields[field] is not None:
            setattr(machine, field, fields[field])
            update_fields.append(field)

    if machine.category not in Machine.Category.values:
        raise ValidationError({"category": f"category must be one of {Machine.Category.values}."})
    if machine.avg_hours_per_day <= 0:
        raise ValidationError({"avg_hours_per_day": "Average hours per day must be greater than zero."})
    if machine.working_days_per_month <= 0:
        raise ValidationError({"working_days_per_month": "Working days per month must be greater than zero."})
    if machine.monthly_repair_cost < 0:
        raise ValidationError({"monthly_repair_cost": "Monthly repair cost cannot be negative."})

    machine.updated_by = user
    machine.save(update_fields=update_fields)

    repair_cost_delta = machine.monthly_repair_cost - old_monthly_repair_cost
    if repair_cost_delta != 0:
        ManufacturingCostsStats.objects.filter(pk=1).update(
            total_estimated_monthly_foh=F("total_estimated_monthly_foh") + repair_cost_delta,
        )

    setting = FactoryOverheadSetting.get_instance()
    _recompute_all_machine_rates(rent_amount=setting.rent_amount, electricity_amount=setting.electricity_amount)
    machine.refresh_from_db(fields=["rate_per_hour"])
    return machine


@transaction.atomic
def delete_machine(*, pk: int, user) -> None:
    machine = Machine.objects.get(pk=pk, is_deleted=False)
    _soft_delete(machine, user)

    ManufacturingCostsStats.objects.filter(pk=1).update(
        total_machines=F("total_machines") - 1,
        total_estimated_monthly_foh=F("total_estimated_monthly_foh") - machine.monthly_repair_cost,
    )

    setting = FactoryOverheadSetting.get_instance()
    _recompute_all_machine_rates(rent_amount=setting.rent_amount, electricity_amount=setting.electricity_amount)


# ---------------------------------------------------------------------------
# Factory Overhead setting (Rent / Electricity)
# ---------------------------------------------------------------------------

@transaction.atomic
def update_factory_overhead_setting(*, rent_amount: Decimal = None, electricity_amount: Decimal = None, user) -> FactoryOverheadSetting:
    """
    rent_amount/electricity_amount default to 0 — a caller passing None
    leaves that field unchanged; explicitly passing 0 resets it to zero
    (both are always valid, deliberate states, never treated as "missing").
    Any change here cascades into every Machine.rate_per_hour immediately.
    """
    from rest_framework.exceptions import ValidationError

    FactoryOverheadSetting.get_instance()  # ensure the singleton row exists
    setting = FactoryOverheadSetting.objects.select_for_update().get(pk=1)
    update_fields = ["updated_by", "updated_at"]
    old_rent, old_electricity = setting.rent_amount, setting.electricity_amount

    if rent_amount is not None:
        if rent_amount < 0:
            raise ValidationError({"rent_amount": "Rent cannot be negative."})
        setting.rent_amount = rent_amount
        update_fields.append("rent_amount")
    if electricity_amount is not None:
        if electricity_amount < 0:
            raise ValidationError({"electricity_amount": "Electricity cannot be negative."})
        setting.electricity_amount = electricity_amount
        update_fields.append("electricity_amount")

    setting.updated_by = user
    setting.save(update_fields=update_fields)

    foh_delta = (setting.rent_amount - old_rent) + (setting.electricity_amount - old_electricity)
    if foh_delta != 0:
        ManufacturingCostsStats.get_instance()
        ManufacturingCostsStats.objects.filter(pk=1).update(
            total_estimated_monthly_foh=F("total_estimated_monthly_foh") + foh_delta,
        )

    _recompute_all_machine_rates(rent_amount=setting.rent_amount, electricity_amount=setting.electricity_amount)
    return setting


# ---------------------------------------------------------------------------
# PayableEntity — rent/electricity singleton bootstrap, delete guard
# ---------------------------------------------------------------------------

def get_or_create_fixed_entity(*, type: str) -> PayableEntity:
    """Lazily get-or-creates the one-and-only Rent/Electricity PayableEntity row. Idempotent."""
    entity, _ = PayableEntity.objects.get_or_create(type=type, employee=None, machine=None)
    return entity


@transaction.atomic
def delete_payable_entity(*, pk: int, user) -> None:
    """
    Backend-enforced guard (not just a hidden frontend button): a
    PayableEntity can only be soft-deleted AFTER its own source
    Employee/Machine has already been soft-deleted — Rent/Electricity's
    fixed rows can never be deleted at all (there's no "source" to delete
    first). Deleting the entity NEVER touches or reverses its Payment
    history — only deleting a specific Payment itself does that.
    """
    from rest_framework.exceptions import ValidationError

    entity = PayableEntity.objects.select_related("employee", "machine").get(pk=pk, is_deleted=False)

    if entity.type == PayableEntity.Type.EMPLOYEE:
        if entity.employee is None or not entity.employee.is_deleted:
            raise ValidationError({"entity": "Delete the employee first before deleting this record."})
    elif entity.type == PayableEntity.Type.MACHINE:
        if entity.machine is None or not entity.machine.is_deleted:
            raise ValidationError({"entity": "Delete the machine first before deleting this record."})
    else:
        raise ValidationError({"entity": "Rent and Electricity records can't be deleted."})

    _soft_delete_payable_entity(entity, user)


def _soft_delete_payable_entity(entity: PayableEntity, user) -> None:
    entity.is_deleted = True
    entity.deleted_at = timezone.now()
    entity.deleted_by = user
    entity.save(update_fields=["is_deleted", "deleted_at", "deleted_by"])


# ---------------------------------------------------------------------------
# Payment — the only thing in this app that touches cash-in-hand
# ---------------------------------------------------------------------------

def _movement_type_for(entity: PayableEntity) -> str:
    return "direct_labor_payment" if entity.type == PayableEntity.Type.EMPLOYEE else "factory_overhead_payment"


def _ensure_this_month_counters_current() -> str:
    """
    Resets this_month_dl_paid/this_month_foh_paid to 0 the moment the real
    calendar month has rolled past what they currently represent — called at
    the start of every Payment write AND every stats read, same "tick on
    read/write, no cron" idiom as this app's other catch-up mechanisms.
    Returns the current period string so callers don't recompute it twice.
    """
    today = timezone.localdate()
    current_period = f"{today.year:04d}-{today.month:02d}"
    stats = ManufacturingCostsStats.get_instance()
    if stats.this_month_period != current_period:
        ManufacturingCostsStats.objects.filter(pk=1).update(
            this_month_period=current_period, this_month_dl_paid=0, this_month_foh_paid=0,
        )
    return current_period


@transaction.atomic
def create_payment(*, entity_id: int, amount: Decimal, payment_date, note: str = "", method_allocations: list, user) -> Payment:
    from rest_framework.exceptions import ValidationError
    from cash_flow.services import (
        record_cash_movement, sync_direct_labor_payment_made, sync_factory_overhead_payment_made,
    )
    from payment_methods.services import record_allocations

    if amount is None or amount <= 0:
        raise ValidationError({"amount": "Amount must be greater than zero."})

    entity = PayableEntity.objects.select_for_update().get(pk=entity_id, is_deleted=False)

    payment = Payment.objects.create(
        reference_number=_next_payment_reference(),
        entity=entity, amount=amount, payment_date=payment_date, note=note or "",
        created_by=user, updated_by=user,
    )

    PayableEntity.objects.filter(pk=entity.pk).update(
        overall_total_paid=F("overall_total_paid") + amount,
        overall_payment_count=F("overall_payment_count") + 1,
    )

    # Only a payment dated WITHIN the current calendar month feeds the "this
    # month so far" running total — a backdated entry for a past month must
    # not distort it (that past month's own figure was already frozen by
    # catch_up_manufacturing_costs_snapshots).
    current_period = _ensure_this_month_counters_current()
    payment_period = f"{payment_date.year:04d}-{payment_date.month:02d}"
    if payment_period == current_period:
        field = "this_month_dl_paid" if entity.type == PayableEntity.Type.EMPLOYEE else "this_month_foh_paid"
        ManufacturingCostsStats.objects.filter(pk=1).update(**{field: F(field) + amount})

    if entity.type == PayableEntity.Type.EMPLOYEE:
        sync_direct_labor_payment_made(amount=amount, user=user)
    else:
        sync_factory_overhead_payment_made(amount=amount, user=user)

    record_cash_movement(payment)
    record_allocations(
        payment, direction="outflow", splits=method_allocations,
        total_amount=amount, date=payment_date, user=user,
    )

    return payment


@transaction.atomic
def delete_payment(*, pk: int, user) -> None:
    from cash_flow.services import (
        reverse_cash_movement, sync_direct_labor_payment_deleted, sync_factory_overhead_payment_deleted,
    )
    from payment_methods.services import reverse_allocations

    payment = Payment.objects.select_related("entity").select_for_update().get(pk=pk, is_deleted=False)
    entity = payment.entity

    if entity.type == PayableEntity.Type.EMPLOYEE:
        sync_direct_labor_payment_deleted(amount=payment.amount, user=user)
    else:
        sync_factory_overhead_payment_deleted(amount=payment.amount, user=user)

    reverse_cash_movement(payment)
    reverse_allocations(payment)

    PayableEntity.objects.filter(pk=entity.pk).update(
        overall_total_paid=F("overall_total_paid") - payment.amount,
        overall_payment_count=F("overall_payment_count") - 1,
    )

    current_period = _ensure_this_month_counters_current()
    payment_period = f"{payment.payment_date.year:04d}-{payment.payment_date.month:02d}"
    if payment_period == current_period:
        field = "this_month_dl_paid" if entity.type == PayableEntity.Type.EMPLOYEE else "this_month_foh_paid"
        ManufacturingCostsStats.objects.filter(pk=1).update(**{field: F(field) - payment.amount})

    _soft_delete(payment, user)


# ---------------------------------------------------------------------------
# Monthly snapshot catch-up — mirrors assets.catch_up_all_asset_depreciation
# exactly: one O(1) global marker gates a per-entity sweep, unique
# constraint + savepoint makes concurrent catch-ups race-safe.
# ---------------------------------------------------------------------------

def catch_up_manufacturing_costs_snapshots() -> int:
    """
    Freezes a PayableEntityMonthlySnapshot for every (entity, closed month)
    combination that doesn't have one yet. Called from every read path in
    this app's selectors, same "tick happens whenever anyone looks" idiom
    as assets/profits/recurring_expenses. Returns how many snapshot rows
    were created (0 most of the time — a single query, no iteration).
    """
    from django.db import IntegrityError
    from django.db.models import Sum

    today = timezone.localdate()
    current_period = f"{today.year:04d}-{today.month:02d}"

    flow = ManufacturingCostsFlow.get_instance()
    if flow.snapshots_caught_up_through == current_period:
        return 0

    created_count = 0
    entities = PayableEntity.objects.all()  # deleted entities can still have unclosed periods to freeze
    for entity in entities:
        last_snapshot = entity.monthly_snapshots.order_by("-period").first()
        if last_snapshot:
            next_period = _add_month(last_snapshot.period)
        else:
            first_payment = entity.payments.filter(is_deleted=False).order_by("payment_date").first()
            if not first_payment:
                continue
            next_period = f"{first_payment.payment_date.year:04d}-{first_payment.payment_date.month:02d}"

        while next_period < current_period:
            first_day, last_day = _period_bounds(next_period)
            total = entity.payments.filter(
                is_deleted=False, payment_date__gte=first_day, payment_date__lte=last_day,
            ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

            try:
                with transaction.atomic():
                    PayableEntityMonthlySnapshot.objects.create(entity=entity, period=next_period, total_paid=total)
                created_count += 1
            except IntegrityError:
                pass  # a concurrent catch-up already froze this period — fine

            next_period = _add_month(next_period)

    # Stamp the Overview page's "last month" figures — a single bounded
    # aggregate over PayableEntityMonthlySnapshot rows for the one just-
    # closed period (bounded by entity count, never by payment history), NOT
    # a live scan of Payment rows. Snapshots for that period are guaranteed
    # to exist by this point (the while loop above always reaches next_period
    # == current_period, i.e. covers every period strictly before it).
    last_month_period = _previous_month(current_period)
    dl_total = PayableEntityMonthlySnapshot.objects.filter(
        period=last_month_period, entity__type=PayableEntity.Type.EMPLOYEE,
    ).aggregate(total=Sum("total_paid"))["total"] or Decimal("0")
    foh_total = PayableEntityMonthlySnapshot.objects.filter(
        period=last_month_period,
        entity__type__in=[PayableEntity.Type.MACHINE, PayableEntity.Type.RENT, PayableEntity.Type.ELECTRICITY],
    ).aggregate(total=Sum("total_paid"))["total"] or Decimal("0")
    ManufacturingCostsStats.get_instance()
    ManufacturingCostsStats.objects.filter(pk=1).update(last_month_dl_paid=dl_total, last_month_foh_paid=foh_total)

    ManufacturingCostsFlow.objects.filter(pk=1).update(snapshots_caught_up_through=current_period)
    return created_count


def _add_month(period: str) -> str:
    y, m = (int(p) for p in period.split("-"))
    if m == 12:
        return f"{y + 1:04d}-01"
    return f"{y:04d}-{m + 1:02d}"


def _previous_month(period: str) -> str:
    y, m = (int(p) for p in period.split("-"))
    if m == 1:
        return f"{y - 1:04d}-12"
    return f"{y:04d}-{m - 1:02d}"


def _period_bounds(period: str):
    import calendar
    y, m = (int(p) for p in period.split("-"))
    last_day_num = calendar.monthrange(y, m)[1]
    return (f"{y:04d}-{m:02d}-01", f"{y:04d}-{m:02d}-{last_day_num:02d}")
