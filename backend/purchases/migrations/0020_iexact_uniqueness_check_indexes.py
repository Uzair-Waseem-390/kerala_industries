from django.db import migrations

# (table, column) pairs whose write-serializer validate_* does a
# `<column>__iexact=` uniqueness pre-check, backed by a case-SENSITIVE
# unique=True B-tree at the DB level. Two effects of that mismatch:
#
# 1. Performance: Django compiles __iexact on PostgreSQL to
#    `UPPER(col) = UPPER(%s)`, which the plain unique B-tree cannot serve
#    (forces a sequential scan under that predicate).
# 2. Correctness: the serializer's check-then-act uniqueness pre-check
#    can race — two near-simultaneous creates of the SAME case can both
#    pass .exists() and then rely on the DB's unique=True constraint to
#    reject the loser (converted to a clean 400 by services._unique_constraint_guard)
#    but two creates that differ only in CASE (e.g. "Yellow" / "yellow")
#    never hit the case-sensitive constraint at all — both succeed,
#    silently violating the business rule the serializer declares.
#
# A UNIQUE functional index on UPPER(col) fixes both: it's what the
# __iexact query can use, AND it makes the database itself enforce the
# same case-insensitive uniqueness the serializer already promises, so
# _unique_constraint_guard's IntegrityError catch closes the race for
# real instead of only for exact-case collisions.
_INDEXED_COLUMNS = [
    ("purchases_shelf", "name"),
    ("purchases_supplier", "code"),
    ("purchases_jumboname", "value"),
    ("purchases_corename", "value"),
    ("purchases_corelength", "value"),
    ("purchases_corethickness", "value"),
    ("purchases_packingsize", "value"),
    ("purchases_cartonsize", "value"),
]


def create_iexact_indexes(apps, schema_editor):
    """
    PostgreSQL-only, same reasoning as 0010_product_trigram_search_indexes.py:
    no-op on SQLite (local dev/tests).

    IMPORTANT for whoever applies this against a populated production
    database: CREATE UNIQUE INDEX will FAIL if any of these 9 columns
    already has an existing case-variant duplicate (e.g. both "Cash" and
    "cash" present, soft-deleted rows included since is_deleted isn't part
    of the index predicate). These are all small, mostly-admin-curated
    lookup tables so this is unlikely, but wasn't verifiable from a
    dev-only session with no Postgres access — check for duplicates first
    (`SELECT UPPER(col), COUNT(*) FROM table GROUP BY UPPER(col) HAVING COUNT(*) > 1`)
    if this migration fails to apply.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    for table, column in _INDEXED_COLUMNS:
        schema_editor.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{table}_{column}_upper "
            f"ON {table} (UPPER({column}));"
        )


def drop_iexact_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table, column in _INDEXED_COLUMNS:
        schema_editor.execute(f"DROP INDEX IF EXISTS idx_{table}_{column}_upper;")


class Migration(migrations.Migration):

    dependencies = [
        ("purchases", "0019_alter_product_category_cartonsize_corelength_and_more"),
    ]

    operations = [
        migrations.RunPython(create_iexact_indexes, drop_iexact_indexes),
    ]
