# Step 1 of 3 — add rm_product/fg_product nullable, keep the old `product`
# field untouched so existing data survives. See 0004 (backfill) and 0005
# (drop `product`, add constraints) — mirrors the WipProduct.code two-step
# migration pattern used earlier in this project for the same reason: real
# existing rows (19 UnpricedProduct rows in dev) can't be safely mapped by
# a single auto-generated RemoveField+AddField migration, which would leave
# every row with both new FKs null and fail the CHECK constraint instantly.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('production', '0014_recipe_labor_machine_and_full_cost'),
        ('purchases', '0027_alter_lostinventoryitem_unique_together_and_more'),
        ('rates', '0002_unpricedproduct'),
    ]

    operations = [
        migrations.AddField(
            model_name='productrate',
            name='fg_product',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='rate', to='production.fgproduct'),
        ),
        migrations.AddField(
            model_name='productrate',
            name='rm_product',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='rate_new', to='purchases.product'),
        ),
        migrations.AddField(
            model_name='productratehistory',
            name='fg_product',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='rate_history', to='production.fgproduct'),
        ),
        migrations.AddField(
            model_name='productratehistory',
            name='rm_product',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='rate_history_new', to='purchases.product'),
        ),
        migrations.AddField(
            model_name='unpricedproduct',
            name='fg_product',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='unpriced_entry', to='production.fgproduct'),
        ),
        migrations.AddField(
            model_name='unpricedproduct',
            name='rm_product',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='unpriced_entry_new', to='purchases.product'),
        ),
    ]
