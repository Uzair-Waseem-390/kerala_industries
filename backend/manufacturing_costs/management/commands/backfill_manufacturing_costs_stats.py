from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Sum

from manufacturing_costs.models import (
    Employee, FactoryOverheadSetting, Machine, ManufacturingCostsStats,
)


class Command(BaseCommand):
    help = (
        "Rebuilds the ManufacturingCostsStats singleton (total_employees, total_machines, "
        "total_estimated_monthly_dl, total_estimated_monthly_foh) from scratch, from current "
        "Employee/Machine/FactoryOverheadSetting rows. Idempotent — safe to re-run any time. "
        "Does NOT touch last_month_dl_paid/last_month_foh_paid — those are stamped by "
        "catch_up_manufacturing_costs_snapshots on the next read, from PayableEntityMonthlySnapshot."
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

        stats = ManufacturingCostsStats.get_instance()
        stats.total_employees = total_employees
        stats.total_machines = total_machines
        stats.total_estimated_monthly_dl = total_dl
        stats.total_estimated_monthly_foh = total_foh
        stats.save(update_fields=[
            "total_employees", "total_machines", "total_estimated_monthly_dl", "total_estimated_monthly_foh",
        ])

        self.stdout.write(self.style.SUCCESS(
            f"ManufacturingCostsStats rebuilt: {total_employees} employees, {total_machines} machines, "
            f"estimated monthly DL={total_dl}, estimated monthly FOH={total_foh} "
            f"(machine repair total={machine_repair_total} + rent={setting.rent_amount} + electricity={setting.electricity_amount})"
        ))
