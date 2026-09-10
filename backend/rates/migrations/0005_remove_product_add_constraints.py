# Step 3 of 3 — drop the old `product` field (every row already backfilled
# into rm_product by 0004), rename rm_product's related_name from the
# temporary "*_new" placeholder to its real final name (couldn't use the
# real name in 0003 while `product` still held it), then add the exactly-
# one-set CHECK constraints and swap the old single-column rate-history
# index for the two new per-type ones.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rates', '0004_backfill_rm_product'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='productratehistory',
            name='idx_rate_history_product_date',
        ),
        migrations.RemoveField(
            model_name='productrate',
            name='product',
        ),
        migrations.RemoveField(
            model_name='unpricedproduct',
            name='product',
        ),
        migrations.RemoveField(
            model_name='productratehistory',
            name='product',
        ),
        migrations.AlterField(
            model_name='productrate',
            name='rm_product',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='rate', to='purchases.product'),
        ),
        migrations.AlterField(
            model_name='productratehistory',
            name='rm_product',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='rate_history', to='purchases.product'),
        ),
        migrations.AlterField(
            model_name='unpricedproduct',
            name='rm_product',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='unpriced_entry', to='purchases.product'),
        ),
        migrations.AlterModelOptions(
            name='productrate',
            options={'ordering': ['id'], 'verbose_name': 'Product Rate', 'verbose_name_plural': 'Product Rates'},
        ),
        migrations.AlterModelOptions(
            name='unpricedproduct',
            options={'ordering': ['id'], 'verbose_name': 'Unpriced Product', 'verbose_name_plural': 'Unpriced Products'},
        ),
        migrations.AddIndex(
            model_name='productratehistory',
            index=models.Index(fields=['rm_product', '-changed_at'], name='idx_rate_hist_rm_prod_date'),
        ),
        migrations.AddIndex(
            model_name='productratehistory',
            index=models.Index(fields=['fg_product', '-changed_at'], name='idx_rate_hist_fg_prod_date'),
        ),
        migrations.AddConstraint(
            model_name='productrate',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('rm_product__isnull', False), ('fg_product__isnull', True)), models.Q(('rm_product__isnull', True), ('fg_product__isnull', False)), _connector='OR'), name='productrate_exactly_one_product'),
        ),
        migrations.AddConstraint(
            model_name='productratehistory',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('rm_product__isnull', False), ('fg_product__isnull', True)), models.Q(('rm_product__isnull', True), ('fg_product__isnull', False)), _connector='OR'), name='productratehistory_exactly_one_product'),
        ),
        migrations.AddConstraint(
            model_name='unpricedproduct',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('rm_product__isnull', False), ('fg_product__isnull', True)), models.Q(('rm_product__isnull', True), ('fg_product__isnull', False)), _connector='OR'), name='unpricedproduct_exactly_one_product'),
        ),
    ]
