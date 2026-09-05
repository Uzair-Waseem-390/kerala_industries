from django.db import migrations


def create_trigram_indexes(apps, schema_editor):
    """
    Trigram (pg_trgm) GIN indexes so search_q()'s icontains-style matching
    on ProductRegistryEntry.name/code is index-backed instead of a full
    table scan — every other searched product table in this codebase
    already has this (purchases_product, production_recipe,
    production_wipproduct, production_fgproduct); this table was the odd
    one out, caught by audit. PostgreSQL-only — no-op on SQLite (local
    dev/tests).
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    schema_editor.execute(
        "CREATE INDEX IF NOT EXISTS idx_registryentry_name_trgm "
        "ON inventory_productregistryentry USING gin (upper(name) gin_trgm_ops);"
    )
    schema_editor.execute(
        "CREATE INDEX IF NOT EXISTS idx_registryentry_code_trgm "
        "ON inventory_productregistryentry USING gin (upper(code) gin_trgm_ops);"
    )


def drop_trigram_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("DROP INDEX IF EXISTS idx_registryentry_name_trgm;")
    schema_editor.execute("DROP INDEX IF EXISTS idx_registryentry_code_trgm;")


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0009_productregistryentry"),
    ]

    operations = [
        migrations.RunPython(create_trigram_indexes, drop_trigram_indexes),
    ]
