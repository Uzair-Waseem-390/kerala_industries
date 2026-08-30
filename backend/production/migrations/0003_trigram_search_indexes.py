from django.db import migrations


def create_trigram_indexes(apps, schema_editor):
    """
    Trigram (pg_trgm) GIN indexes so search_q()'s icontains-style matching
    on Recipe.recipe_number/name and WipProduct.name is index-backed instead
    of a full table scan. Mirrors purchases/migrations/0010_product_trigram_search_indexes.py.
    PostgreSQL-only — no-op on SQLite (local dev/tests).
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    schema_editor.execute(
        "CREATE INDEX IF NOT EXISTS idx_recipe_number_trgm "
        "ON production_recipe USING gin (upper(recipe_number) gin_trgm_ops);"
    )
    schema_editor.execute(
        "CREATE INDEX IF NOT EXISTS idx_recipe_name_trgm "
        "ON production_recipe USING gin (upper(name) gin_trgm_ops);"
    )
    schema_editor.execute(
        "CREATE INDEX IF NOT EXISTS idx_wipproduct_name_trgm "
        "ON production_wipproduct USING gin (upper(name) gin_trgm_ops);"
    )


def drop_trigram_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("DROP INDEX IF EXISTS idx_recipe_number_trgm;")
    schema_editor.execute("DROP INDEX IF EXISTS idx_recipe_name_trgm;")
    schema_editor.execute("DROP INDEX IF EXISTS idx_wipproduct_name_trgm;")


class Migration(migrations.Migration):

    dependencies = [
        ("production", "0002_recipe_created_at_index"),
    ]

    operations = [
        migrations.RunPython(create_trigram_indexes, drop_trigram_indexes),
    ]
