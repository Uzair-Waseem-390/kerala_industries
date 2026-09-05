# Paired half of inventory.0005_add_wip_models's SeparateDatabaseAndState
# move — removes WipInventory, WipShelfStock, WipShelfStockMovement from
# PRODUCTION's model state only. No real DDL runs (state_operations only,
# empty database_operations) — the underlying tables are untouched and now
# belong to the inventory app's state (see inventory/models.py's Meta.db_table
# pins). Depends on inventory's migration so the models are never absent
# from both apps' state at once.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('production', '0008_alter_recipe_finished_at_and_more'),
        ('inventory', '0005_add_wip_models'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='WipShelfStockMovement'),
                migrations.DeleteModel(name='WipShelfStock'),
                migrations.DeleteModel(name='WipInventory'),
            ],
            database_operations=[],
        ),
    ]
