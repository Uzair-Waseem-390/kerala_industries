import django.db.models.deletion
from django.db import migrations, models


def backfill_variant_key(apps, schema_editor):
    """
    Every existing Product row today is one of the 4 canonical family-anchor
    rows (base_product=None, no attributes) — variant_key for each is
    derived from its own `code` (already unique=True on its own), matching
    purchases.utils.compute_anchor_variant_key's exact format so future
    create_product() calls stay consistent with what this backfill wrote.
    """
    Product = apps.get_model("purchases", "Product")
    for product in Product.objects.all():
        product.variant_key = f"anchor:{product.code}"
        product.save(update_fields=["variant_key"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("purchases", "0024_alter_lostinventoryfifoconsumption_quantity_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="base_product",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="variants", to="purchases.product"),
        ),
        migrations.AddField(
            model_name="product",
            name="jumbo_name",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="products", to="purchases.jumboname"),
        ),
        migrations.AddField(
            model_name="product",
            name="core_name",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="products", to="purchases.corename"),
        ),
        migrations.AddField(
            model_name="product",
            name="core_length",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="products", to="purchases.corelength"),
        ),
        migrations.AddField(
            model_name="product",
            name="core_thickness",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="products", to="purchases.corethickness"),
        ),
        migrations.AddField(
            model_name="product",
            name="packing_size",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="products", to="purchases.packingsize"),
        ),
        migrations.AddField(
            model_name="product",
            name="carton_size",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="products", to="purchases.cartonsize"),
        ),
        migrations.AddField(
            model_name="product",
            name="variant_key",
            field=models.CharField(default="", editable=False, max_length=500),
            preserve_default=False,
        ),
        migrations.RunPython(backfill_variant_key, noop_reverse),
        migrations.AlterField(
            model_name="product",
            name="variant_key",
            field=models.CharField(editable=False, max_length=500, unique=True),
        ),
    ]
