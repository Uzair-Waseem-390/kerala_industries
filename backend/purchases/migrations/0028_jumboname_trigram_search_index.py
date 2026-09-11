from django.db import migrations

# JumboName.value is now searched via search_q() in get_all_jumbo_names()
# (data_entry's WIP/FG opening-stock "Name" picker, 2026-09, switched from a
# client-side-filtered prefetch to backend search) — every search_q-targeted
# column needs a matching trigram index (see
# instructions/architecture.md "Indexed search always"). Same pattern as
# 0013_shelf_name_trigram_index.py.
_TRIGRAM_TARGETS = [
    ("purchases_jumboname", "value"),
]


def create_trigram_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    for table, column in _TRIGRAM_TARGETS:
        schema_editor.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{table}_{column}_trgm "
            f"ON {table} USING gin (upper({column}) gin_trgm_ops);"
        )


def drop_trigram_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table, column in _TRIGRAM_TARGETS:
        schema_editor.execute(f"DROP INDEX IF EXISTS idx_{table}_{column}_trgm;")


class Migration(migrations.Migration):

    dependencies = [
        ("purchases", "0027_alter_lostinventoryitem_unique_together_and_more"),
    ]

    operations = [
        migrations.RunPython(create_trigram_indexes, drop_trigram_indexes),
    ]
