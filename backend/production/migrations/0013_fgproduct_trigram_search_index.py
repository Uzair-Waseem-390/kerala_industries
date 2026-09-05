from django.db import migrations


def create_trigram_index(apps, schema_editor):
    """
    Trigram (pg_trgm) GIN index so search_q()'s icontains-style matching on
    FgProduct.name is index-backed instead of a full table scan — the FG
    twin of 0003_trigram_search_indexes.py's idx_wipproduct_name_trgm,
    missed when FgProduct was first added. PostgreSQL-only — no-op on
    SQLite (local dev/tests).
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    schema_editor.execute(
        "CREATE INDEX IF NOT EXISTS idx_fgproduct_name_trgm "
        "ON production_fgproduct USING gin (upper(name) gin_trgm_ops);"
    )


def drop_trigram_index(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("DROP INDEX IF EXISTS idx_fgproduct_name_trgm;")


class Migration(migrations.Migration):

    dependencies = [
        ("production", "0012_rename_packingpiececonsumption_issued_material"),
    ]

    operations = [
        migrations.RunPython(create_trigram_index, drop_trigram_index),
    ]
