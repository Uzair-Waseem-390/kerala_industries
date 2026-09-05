from django.db import migrations


def backfill_variant_key_stage(apps, schema_editor):
    """
    compute_wip_variant_key now includes `stage` in the fingerprint (see
    production.utils) so a whole Rewound Core and a Cut Piece can never
    collide into the same row even if their numeric attributes happen to
    match. Every WipProduct row created before this migration was created by
    Rewinding (Cutting didn't exist yet), so backfilling "|stage=rewinding"
    onto its existing variant_key reproduces exactly what
    compute_wip_variant_key would compute for it now — get_or_create lookups
    keep matching the same row instead of spawning a duplicate.
    Includes soft-deleted rows (all_objects-equivalent) since variant_key's
    uniqueness constraint covers them too.
    """
    WipProduct = apps.get_model("production", "WipProduct")
    for wp in WipProduct.objects.all():
        if not wp.variant_key.endswith("|stage=" + wp.stage):
            wp.variant_key = f"{wp.variant_key}|stage={wp.stage}"
            wp.save(update_fields=["variant_key"])


def reverse(apps, schema_editor):
    WipProduct = apps.get_model("production", "WipProduct")
    for wp in WipProduct.objects.all():
        suffix = f"|stage={wp.stage}"
        if wp.variant_key.endswith(suffix):
            wp.variant_key = wp.variant_key[: -len(suffix)]
            wp.save(update_fields=["variant_key"])


class Migration(migrations.Migration):

    dependencies = [
        ("production", "0006_recipe_waste_cost_recipe_waste_length_mm_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_variant_key_stage, reverse),
    ]
