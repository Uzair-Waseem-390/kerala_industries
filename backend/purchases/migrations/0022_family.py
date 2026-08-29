import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def seed_families_and_backfill_products(apps, schema_editor):
    """
    Seeds the 3 fixed Family rows (Raw Material, WIP, Finished Goods) and
    backfills every existing Product row to family="Raw Material" — the
    only stage that exists today. Safe against a fresh/empty DB (nothing to
    backfill) and against this project's already-seeded 4 products alike.
    """
    Family = apps.get_model("purchases", "Family")
    Product = apps.get_model("purchases", "Product")

    for name in ["Raw Material", "WIP", "Finished Goods"]:
        Family.objects.get_or_create(name=name)

    raw_material = Family.objects.get(name="Raw Material")
    Product.objects.filter(family__isnull=True).update(family=raw_material)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("purchases", "0021_remove_product_category_delete_category"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Family",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("name", models.CharField(max_length=255, unique=True)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(class)s_created", to=settings.AUTH_USER_MODEL)),
                ("deleted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(class)s_deleted", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="%(class)s_updated", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Family",
                "verbose_name_plural": "Families",
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="product",
            name="family",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="products", to="purchases.family"),
        ),
        migrations.RunPython(seed_families_and_backfill_products, noop_reverse),
        migrations.AlterField(
            model_name="product",
            name="family",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="products", to="purchases.family"),
        ),
    ]
