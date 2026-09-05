# Mechanical extraction of WipInventory, WipShelfStock, WipShelfStockMovement
# out of the production app — mirrors purchases -> inventory's own extraction
# (inventory/migrations/0001_initial.py). SeparateDatabaseAndState — model
# STATE gains these three models here, but no real DDL runs (state_operations
# only). The tables already exist (created by production's own migration
# history) with the exact db_table names pinned in this app's models.py, so
# this is a pure app-ownership relabel: zero rows moved, zero columns changed.
#
# The paired migration in production (which removes these three models from
# ITS state) depends on this one, so the models never exist in neither app's
# state at once.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0004_recipe_issue_consumption_reason'),
        ('production', '0008_alter_recipe_finished_at_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='WipInventory',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('quantity', models.DecimalField(db_index=True, decimal_places=4, default=0, max_digits=14)),
                        ('last_updated_at', models.DateTimeField(auto_now=True)),
                        ('last_updated_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='wip_inventory_updates', to=settings.AUTH_USER_MODEL)),
                        ('product', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='inventory', to='production.wipproduct')),
                    ],
                    options={
                        'verbose_name': 'WIP Inventory',
                        'verbose_name_plural': 'WIP Inventories',
                        'ordering': ['product__name'],
                        'db_table': 'production_wipinventory',
                    },
                ),
                migrations.CreateModel(
                    name='WipShelfStock',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('quantity', models.DecimalField(decimal_places=4, default=0, max_digits=14)),
                        ('last_updated_at', models.DateTimeField(auto_now=True)),
                        ('product', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='shelf_stock_rows', to='production.wipproduct')),
                        ('shelf', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='wip_stock_rows', to='purchases.shelf')),
                    ],
                    options={
                        'verbose_name': 'WIP Shelf Stock',
                        'verbose_name_plural': 'WIP Shelf Stock',
                        'db_table': 'production_wipshelfstock',
                        'unique_together': {('shelf', 'product')},
                    },
                ),
                migrations.CreateModel(
                    name='WipShelfStockMovement',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('delta', models.DecimalField(decimal_places=4, help_text='Positive = added to shelf, negative = removed from shelf.', max_digits=14)),
                        ('reason', models.CharField(choices=[('recipe_breakdown_putaway', 'Recipe Breakdown Put-Away'), ('cutting_issue_consumption', 'Cutting Issue Consumption'), ('cutting_breakdown_putaway', 'Cutting Breakdown Put-Away')], db_index=True, max_length=30)),
                        ('reference', models.CharField(blank=True, default='', help_text='e.g. REC-2026-0001', max_length=30)),
                        ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                        ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='wip_shelf_stock_movements', to=settings.AUTH_USER_MODEL)),
                        ('product', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='shelf_movements', to='production.wipproduct')),
                        ('shelf', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='wip_movements', to='purchases.shelf')),
                    ],
                    options={
                        'verbose_name': 'WIP Shelf Stock Movement',
                        'verbose_name_plural': 'WIP Shelf Stock Movements',
                        'ordering': ['-created_at'],
                        'db_table': 'production_wipshelfstockmovement',
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
