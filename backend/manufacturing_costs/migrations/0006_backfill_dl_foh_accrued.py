from decimal import Decimal

from django.db import migrations


def backfill_total_dl_foh_accrued(apps, schema_editor):
    """
    ManufacturingCostsStats.total_dl_foh_accrued only started being
    incremented going forward once production.services._shared's 3
    finish_*_recipe call sites were wired up (2026-09, same change that
    added the Accrued Manufacturing Cost Payable Balance Sheet line). Any
    recipe finished before that point never contributed to this counter,
    permanently understating it (and therefore misstating the new liability
    line) unless backfilled once here.

    Re-derives the exact same DL+FOH pool figure
    production.services._shared.compute_labor_overhead_pool computes at
    finish time — labor/machine rate_per_hour_snapshot rows are already
    frozen per recipe (RecipeLabor/RecipeMachine), so this reproduces the
    historical value exactly, not an approximation.
    """
    Recipe = apps.get_model("production", "Recipe")
    ManufacturingCostsStats = apps.get_model("manufacturing_costs", "ManufacturingCostsStats")

    total = Decimal("0")
    for recipe in Recipe.objects.filter(status="finished").prefetch_related("labor_entries", "machine_entries"):
        labor_rate_total = sum(
            (e.rate_per_hour_snapshot for e in recipe.labor_entries.all()), Decimal("0")
        )
        machine_rate_total = sum(
            (m.rate_per_hour_snapshot for m in recipe.machine_entries.all()), Decimal("0")
        )
        total_hours = Decimal(recipe.time_hours) + (Decimal(recipe.time_minutes) / Decimal(60))
        total += (labor_rate_total + machine_rate_total) * total_hours

    stats, _ = ManufacturingCostsStats.objects.get_or_create(pk=1)
    stats.total_dl_foh_accrued = total
    stats.save(update_fields=["total_dl_foh_accrued"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("manufacturing_costs", "0005_manufacturingcostsstats_total_dl_foh_accrued"),
        ("production", "0014_recipe_labor_machine_and_full_cost"),
    ]

    operations = [
        migrations.RunPython(backfill_total_dl_foh_accrued, noop_reverse),
    ]
