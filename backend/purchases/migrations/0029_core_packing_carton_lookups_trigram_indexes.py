from django.db import migrations

# CoreName/CoreLength/CoreThickness/PackingSize/CartonSize.value are now
# searched via search_q() (get_all_core_names/get_all_core_lengths/
# get_all_core_thicknesses/get_all_packing_sizes/get_all_carton_sizes,
# 2026-09 — the Purchase Intake page's attribute pickers switched from a
# client-side-filtered prefetch to backend search) — every search_q-targeted
# column needs a matching trigram index (see
# instructions/architecture.md "Indexed search always"). Same pattern as
# 0028_jumboname_trigram_search_index.py.
_TRIGRAM_TARGETS = [
    ("purchases_corename", "value"),
    ("purchases_corelength", "value"),
    ("purchases_corethickness", "value"),
    ("purchases_packingsize", "value"),
    ("purchases_cartonsize", "value"),
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
        ("purchases", "0028_jumboname_trigram_search_index"),
    ]

    operations = [
        migrations.RunPython(create_trigram_indexes, drop_trigram_indexes),
    ]
