from django.db import migrations


def create_remaining_quantity_index(apps, schema_editor):
    """
    Partial index covering the exact shape both the FIFO batch-lookup
    selector (get_available_purchase_items_for_fifo, filters
    product_id= + remaining_quantity__gt=0, orders by order__confirmed_at)
    and the Inventory Valuation report (same remaining_quantity__gt=0
    filter, bulk by product_id__in=) actually query.

    Partial (WHERE remaining_quantity > 0) rather than a plain composite
    index — as PurchaseItem accumulates history, the vast majority of rows
    end up fully consumed (remaining_quantity=0) via normal FIFO turnover
    and are irrelevant to both consumers; keeping the index scoped to only
    the still-open batches keeps it small and cheap to maintain on every
    FIFO-consuming write, instead of indexing (and re-balancing on every
    write to) rows nobody queries by this shape once they're exhausted.

    PostgreSQL-only, same reasoning as 0010_product_trigram_search_indexes.py:
    on SQLite (local dev/tests) this is a no-op — current table sizes there
    are negligible and SQLite's query planning for this shape isn't the
    concern this index exists to address.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        "CREATE INDEX IF NOT EXISTS idx_purchaseitem_open_batches "
        "ON purchases_purchaseitem (product_id, remaining_quantity) "
        "WHERE remaining_quantity > 0;"
    )


def drop_remaining_quantity_index(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("DROP INDEX IF EXISTS idx_purchaseitem_open_batches;")


class Migration(migrations.Migration):

    dependencies = [
        ("purchases", "0017_remove_inventory_models_state_only"),
    ]

    operations = [
        migrations.RunPython(create_remaining_quantity_index, drop_remaining_quantity_index),
    ]
