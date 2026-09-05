from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Second step of the WIP product code rollout: every existing row was
    backfilled by backfill_wip_product_codes (run manually before this
    migration) before this constraint tightens, so no data-loss risk.
    """

    dependencies = [
        ("production", "0010_wipproduct_code_alter_recipe_recipe_type_fgproduct_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="wipproduct",
            name="code",
            field=models.CharField(editable=False, max_length=30, unique=True),
        ),
    ]
