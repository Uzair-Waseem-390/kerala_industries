from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.utils import timezone

from manufacturing_costs.models import (
    Employee, FactoryOverheadSetting, Machine, ManufacturingCostsStats, PayableEntity, Payment,
)


class Command(BaseCommand):
    help = (
        "Rebuilds the ManufacturingCostsStats singleton (total_employees, total_machines, "
        "total_estimated_monthly_dl, total_estimated_monthly_foh, this_month_dl_paid, "
        "this_month_foh_paid) from scratch, from current Employee/Machine/FactoryOverheadSetting/"
        "Payment rows. Idempotent — safe to re-run any time. Does NOT touch last_month_dl_paid/"
        "last_month_foh_paid — those are stamped by catch_up_manufacturing_costs_snapshots on the "
        "next read, from PayableEntityMonthlySnapshot."
    )

    def handle(self, *args, **kwargs):
        employees = Employee.objects.filter(is_deleted=False)
        machines = Machine.objects.filter(is_deleted=False)
        setting = FactoryOverheadSetting.get_instance()

        total_employees = employees.count()
        total_machines = machines.count()
        total_dl = employees.aggregate(total=Sum("monthly_salary"))["total"] or Decimal("0")
        machine_repair_total = machines.aggregate(total=Sum("monthly_repair_cost"))["total"] or Decimal("0")
        total_foh = machine_repair_total + setting.rent_amount + setting.electricity_amount

        today = timezone.localdate()
        current_period = f"{today.year:04d}-{today.month:02d}"
        month_start = today.replace(day=1)
        this_month_payments = Payment.objects.filter(is_deleted=False, payment_date__gte=month_start, payment_date__lte=today)
        this_month_dl = this_month_payments.filter(
            entity__type=PayableEntity.Type.EMPLOYEE,
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        this_month_foh = this_month_payments.exclude(
            entity__type=PayableEntity.Type.EMPLOYEE,
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

        stats = ManufacturingCostsStats.get_instance()
        stats.total_employees = total_employees
        stats.total_machines = total_machines
        stats.total_estimated_monthly_dl = total_dl
        stats.total_estimated_monthly_foh = total_foh
        stats.this_month_period = current_period
        stats.this_month_dl_paid = this_month_dl
        stats.this_month_foh_paid = this_month_foh
        stats.save(update_fields=[
            "total_employees", "total_machines", "total_estimated_monthly_dl", "total_estimated_monthly_foh",
            "this_month_period", "this_month_dl_paid", "this_month_foh_paid",
        ])

        self.stdout.write(self.style.SUCCESS(
            f"ManufacturingCostsStats rebuilt: {total_employees} employees, {total_machines} machines, "
            f"estimated monthly DL={total_dl}, estimated monthly FOH={total_foh} "
            f"(machine repair total={machine_repair_total} + rent={setting.rent_amount} + electricity={setting.electricity_amount}); "
            f"this month ({current_period}) DL paid={this_month_dl}, FOH paid={this_month_foh}"
        ))
