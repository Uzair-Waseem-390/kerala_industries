# Paired half of inventory.0001_initial's SeparateDatabaseAndState move —
# removes Inventory, ShelfStock, ShelfStockMovement, ProductStockMovement,
# StockMovementFlow, InventoryStatsFlow from PURCHASES' model state only.
# No real DDL runs (state_operations only, empty database_operations) — the
# underlying tables are untouched and now belong to the inventory app's
# state (see inventory/models.py's Meta.db_table pins). Depends on
# inventory's migration so the models are never absent from both apps'
# state at once.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('purchases', '0016_alter_supplierpayment_method'),
        ('inventory', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='ShelfStockMovement'),
                migrations.DeleteModel(name='ShelfStock'),
                migrations.DeleteModel(name='ProductStockMovement'),
                migrations.DeleteModel(name='StockMovementFlow'),
                migrations.DeleteModel(name='InventoryStatsFlow'),
                migrations.DeleteModel(name='Inventory'),
            ],
            database_operations=[],
        ),
    ]
