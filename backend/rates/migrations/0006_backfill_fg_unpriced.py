from django.db import migrations


def backfill_fg_unpriced(apps, schema_editor):
    """
    FG products only started getting an UnpricedProduct row at creation
    time once production.services.packing.finish_packing_recipe was wired
    up to call add_to_unpriced_queue() (2026-09, same change that added
    FG-selling to billing/rates). Any FgProduct that already existed before
    that point has neither a rate nor an unpriced-queue entry, making it
    invisible to the rates app entirely. Backfill those in.
    """
    FgProduct = apps.get_model("production", "FgProduct")
    UnpricedProduct = apps.get_model("rates", "UnpricedProduct")

    missing = FgProduct.objects.filter(
        is_deleted=False, unpriced_entry__isnull=True, rate__isnull=True,
    )
    UnpricedProduct.objects.bulk_create(
        [UnpricedProduct(fg_product=p) for p in missing]
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("rates", "0005_remove_product_add_constraints"),
    ]

    operations = [
        migrations.RunPython(backfill_fg_unpriced, noop_reverse),
    ]
