# Mechanical extraction of Inventory, ShelfStock, ShelfStockMovement,
# ProductStockMovement, StockMovementFlow, InventoryStatsFlow out of the
# purchases app. SeparateDatabaseAndState — Django's model STATE gains these
# six models here, but no real DDL runs (state_operations only). The tables
# already exist (created by purchases' own migration history) with the exact
# db_table names pinned in inventory/models.py's Meta, so this is a pure
# app-ownership relabel: zero rows moved, zero columns changed.
#
# The paired migration in purchases (which removes these six models from
# ITS state) depends on this one, so purchases never has a window where the
# models exist in neither app's state.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('purchases', '0016_alter_supplierpayment_method'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='Inventory',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('quantity', models.PositiveIntegerField(db_index=True, default=0)),
                        ('last_updated_at', models.DateTimeField(auto_now=True)),
                        ('last_updated_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inventory_updates', to=settings.AUTH_USER_MODEL)),
                        ('product', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='inventory', to='purchases.product')),
                    ],
                    options={
                        'verbose_name': 'Inventory',
                        'verbose_name_plural': 'Inventories',
                        'ordering': ['product__name'],
                        'db_table': 'purchases_inventory',
                    },
                ),
                migrations.CreateModel(
                    name='ShelfStock',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('quantity', models.PositiveIntegerField(default=0)),
                        ('last_updated_at', models.DateTimeField(auto_now=True)),
                        ('product', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='shelf_stock_rows', to='purchases.product')),
                        ('shelf', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='stock_rows', to='purchases.shelf')),
                    ],
                    options={
                        'verbose_name': 'Shelf Stock',
                        'verbose_name_plural': 'Shelf Stock',
                        'unique_together': {('shelf', 'product')},
                        'db_table': 'purchases_shelfstock',
                    },
                ),
                migrations.CreateModel(
                    name='ShelfStockMovement',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('delta', models.IntegerField(help_text='Positive = added to shelf, negative = removed from shelf.')),
                        ('reason', models.CharField(choices=[('purchase_putaway', 'Purchase Put-Away'), ('sale_consumption', 'Sale Consumption'), ('invoice_return_putaway', 'Invoice Return Put-Away'), ('purchase_return_consumption', 'Purchase Return Consumption'), ('lost_consumption', 'Lost Inventory Consumption'), ('lost_found_putaway', 'Lost Inventory Found Put-Away'), ('move_out', 'Manual Move (Out)'), ('move_in', 'Manual Move (In)'), ('backfill', 'Backfill')], db_index=True, max_length=30)),
                        ('reference', models.CharField(blank=True, default='', help_text='e.g. PO-2026-0001, BILL-2026-0001', max_length=30)),
                        ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                        ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='shelf_stock_movements', to=settings.AUTH_USER_MODEL)),
                        ('product', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='shelf_movements', to='purchases.product')),
                        ('shelf', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='movements', to='purchases.shelf')),
                    ],
                    options={
                        'verbose_name': 'Shelf Stock Movement',
                        'verbose_name_plural': 'Shelf Stock Movements',
                        'ordering': ['-created_at'],
                        'db_table': 'purchases_shelfstockmovement',
                        'indexes': [
                            models.Index(fields=['shelf', '-created_at'], name='purchases_s_shelf_i_4cb46b_idx'),
                            models.Index(fields=['product', '-created_at'], name='purchases_s_product_5fc577_idx'),
                        ],
                    },
                ),
                migrations.CreateModel(
                    name='ProductStockMovement',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('total_purchased', models.PositiveIntegerField(default=0)),
                        ('total_purchase_returned', models.PositiveIntegerField(default=0)),
                        ('total_sold', models.PositiveIntegerField(default=0)),
                        ('total_sale_returned', models.PositiveIntegerField(default=0)),
                        ('total_lost', models.PositiveIntegerField(default=0)),
                        ('total_found', models.PositiveIntegerField(default=0)),
                        ('last_updated_at', models.DateTimeField(auto_now=True)),
                        ('product', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='stock_movement', to='purchases.product')),
                    ],
                    options={
                        'verbose_name': 'Product Stock Movement',
                        'verbose_name_plural': 'Product Stock Movement',
                        'db_table': 'purchases_productstockmovement',
                    },
                ),
                migrations.CreateModel(
                    name='StockMovementFlow',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('total_purchased', models.PositiveIntegerField(default=0)),
                        ('total_purchase_returned', models.PositiveIntegerField(default=0)),
                        ('total_sold', models.PositiveIntegerField(default=0)),
                        ('total_sale_returned', models.PositiveIntegerField(default=0)),
                        ('total_lost', models.PositiveIntegerField(default=0)),
                        ('total_found', models.PositiveIntegerField(default=0)),
                        ('last_updated_at', models.DateTimeField(auto_now=True)),
                    ],
                    options={
                        'verbose_name': 'Stock Movement Flow',
                        'verbose_name_plural': 'Stock Movement Flow',
                        'db_table': 'purchases_stockmovementflow',
                    },
                ),
                migrations.CreateModel(
                    name='InventoryStatsFlow',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('total_products', models.PositiveIntegerField(default=0)),
                        ('low_stock_count', models.PositiveIntegerField(default=0)),
                        ('out_of_stock_count', models.PositiveIntegerField(default=0)),
                        ('last_updated_at', models.DateTimeField(auto_now=True)),
                    ],
                    options={
                        'verbose_name': 'Inventory Stats Flow',
                        'verbose_name_plural': 'Inventory Stats Flow',
                        'db_table': 'purchases_inventorystatsflow',
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
