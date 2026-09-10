# Step 2 of 3 — every existing row is RM by definition (FG never existed as
# a priceable product type before this migration), so a straight copy of
# the old `product_id` into the new `rm_product_id` is exact, not a guess.

from django.db import migrations, models


def backfill_rm_product(apps, schema_editor):
    for model_name in ("ProductRate", "UnpricedProduct", "ProductRateHistory"):
        model = apps.get_model("rates", model_name)
        model.objects.all().update(rm_product_id=models.F("product_id"))


def reverse_backfill(apps, schema_editor):
    for model_name in ("ProductRate", "UnpricedProduct", "ProductRateHistory"):
        model = apps.get_model("rates", model_name)
        model.objects.all().update(rm_product_id=None, fg_product_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ('rates', '0003_fg_selling_cartons'),
    ]

    operations = [
        migrations.RunPython(backfill_rm_product, reverse_backfill),
    ]
