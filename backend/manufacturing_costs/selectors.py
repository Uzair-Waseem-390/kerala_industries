from decimal import Decimal

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from django.utils import timezone

from backend.search import search_q

from .models import (
    Employee, FactoryOverheadSetting, Machine, PayableEntity,
    PayableEntityMonthlySnapshot, Payment,
)
from .services import catch_up_manufacturing_costs_snapshots, get_or_create_fixed_entity


def _clean(value):
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped if stripped else None


# ---------------------------------------------------------------------------
# Employee
# ---------------------------------------------------------------------------

def get_all_employees(*, search: str = None) -> QuerySet:
    qs = Employee.objects.filter(is_deleted=False).select_related("created_by", "updated_by")
    if _clean(search):
        qs = qs.filter(search_q(_clean(search), "name"))
    return qs


def get_employee_by_id(pk: int) -> Employee:
    return get_object_or_404(Employee.objects.select_related("created_by", "updated_by"), pk=pk, is_deleted=False)


# ---------------------------------------------------------------------------
# Machine
# ---------------------------------------------------------------------------

def get_all_machines(*, search: str = None, category: str = None) -> QuerySet:
    qs = Machine.objects.filter(is_deleted=False).select_related("created_by", "updated_by")
    if _clean(category):
        qs = qs.filter(category=_clean(category))
    if _clean(search):
        qs = qs.filter(search_q(_clean(search), "name"))
    return qs


def get_machine_by_id(pk: int) -> Machine:
    return get_object_or_404(Machine.objects.select_related("created_by", "updated_by"), pk=pk, is_deleted=False)


def get_factory_overhead_setting() -> FactoryOverheadSetting:
    return FactoryOverheadSetting.get_instance()


# ---------------------------------------------------------------------------
# PayableEntity (Page 4) — every read here first runs the O(1)-gated
# monthly-snapshot catch-up, same "tick on read" idiom as assets/profits.
# ---------------------------------------------------------------------------

def get_all_payable_entities(*, search: str = None, type_filter: str = None) -> QuerySet:
    catch_up_manufacturing_costs_snapshots()
    # Ensure the two fixed singleton rows exist before listing — cheap,
    # idempotent get_or_create, not a query that scales with anything.
    get_or_create_fixed_entity(type=PayableEntity.Type.RENT)
    get_or_create_fixed_entity(type=PayableEntity.Type.ELECTRICITY)

    qs = PayableEntity.objects.filter(is_deleted=False).select_related(
        "employee", "employee__created_by", "employee__updated_by",
        "machine", "machine__created_by", "machine__updated_by",
        "deleted_by",
    )
    if _clean(type_filter):
        qs = qs.filter(type=_clean(type_filter))
    if _clean(search):
        qs = qs.filter(
            search_q(_clean(search), "employee__name") | search_q(_clean(search), "machine__name")
        )
    return qs.order_by("type", "employee__name", "machine__name")


def get_payable_entity_by_id(pk: int) -> PayableEntity:
    catch_up_manufacturing_costs_snapshots()
    return get_object_or_404(
        PayableEntity.objects.select_related(
            "employee", "employee__created_by", "employee__updated_by",
            "machine", "machine__created_by", "machine__updated_by",
        ),
        pk=pk, is_deleted=False,
    )


def get_payable_entity_stats(entity: PayableEntity) -> dict:
    """
    O(1)/bounded reads only — overall_average from entity's own stored
    counters (see PayableEntity.overall_average_monthly), last month + last
    3 months from PayableEntityMonthlySnapshot (frozen rows, at most 3
    fetched — never a live SUM over Payment rows).
    """
    today = timezone.localdate()
    last_month_year, last_month_month = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    last_period = f"{last_month_year:04d}-{last_month_month:02d}"

    last_month_snapshot = entity.monthly_snapshots.filter(period=last_period).first()
    recent_snapshots = list(entity.monthly_snapshots.order_by("-period")[:3])
    avg_last_3_months = (
        (sum((s.total_paid for s in recent_snapshots), Decimal("0")) / len(recent_snapshots))
        if recent_snapshots else Decimal("0")
    )

    return {
        "overall_average_monthly": entity.overall_average_monthly,
        "last_month_expense": last_month_snapshot.total_paid if last_month_snapshot else Decimal("0"),
        "avg_last_3_months": avg_last_3_months,
    }


def get_payments_for_entity(entity_id: int, *, search: str = None) -> QuerySet:
    qs = Payment.objects.filter(entity_id=entity_id, is_deleted=False).select_related("created_by")
    if _clean(search):
        qs = qs.filter(search_q(_clean(search), "reference_number"))
    return qs


# ---------------------------------------------------------------------------
# Payments (Page 5)
# ---------------------------------------------------------------------------

def get_all_payments(
    *,
    search    : str = None,
    entity_id : str = None,
    entity_type: str = None,
    date      : str = None,
    date_from : str = None,
    date_to   : str = None,
) -> QuerySet:
    qs = Payment.objects.filter(is_deleted=False).select_related(
        "entity", "entity__employee", "entity__machine", "created_by",
    )
    if _clean(search):
        qs = qs.filter(search_q(_clean(search), "reference_number"))
    if _clean(entity_id):
        qs = qs.filter(entity_id=_clean(entity_id))
    if _clean(entity_type):
        qs = qs.filter(entity__type=_clean(entity_type))
    if _clean(date):
        qs = qs.filter(payment_date=_clean(date))
    if _clean(date_from):
        qs = qs.filter(payment_date__gte=_clean(date_from))
    if _clean(date_to):
        qs = qs.filter(payment_date__lte=_clean(date_to))
    return qs


def get_payment_by_id(pk: int) -> Payment:
    return get_object_or_404(
        Payment.objects.select_related("entity", "entity__employee", "entity__machine", "created_by"),
        pk=pk, is_deleted=False,
    )
