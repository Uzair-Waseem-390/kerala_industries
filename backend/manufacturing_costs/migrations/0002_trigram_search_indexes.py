from django.db import migrations

_TRIGRAM_TARGETS = [
    ("manufacturing_costs_employee", "name",             "idx_mfg_employee_name_trgm"),
    ("manufacturing_costs_machine",  "name",             "idx_mfg_machine_name_trgm"),
    ("manufacturing_costs_payment",  "reference_number", "idx_mfg_payment_reference_trgm"),
]


def create_trigram_indexes(apps, schema_editor):
    """
    Trigram (pg_trgm) GIN expression indexes on upper(col) — matches what
    search_q compiles to on PostgreSQL. No-op on SQLite (dev).
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    for table, column, index_name in _TRIGRAM_TARGETS:
        schema_editor.execute(
            f"CREATE INDEX IF NOT EXISTS {index_name} "
            f"ON {table} USING gin (upper({column}) gin_trgm_ops);"
        )


def drop_trigram_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for _table, _column, index_name in _TRIGRAM_TARGETS:
        schema_editor.execute(f"DROP INDEX IF EXISTS {index_name};")


class Migration(migrations.Migration):

    dependencies = [
        ("manufacturing_costs", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_trigram_indexes, drop_trigram_indexes),
    ]
