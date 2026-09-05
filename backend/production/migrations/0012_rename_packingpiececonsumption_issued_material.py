from django.db import migrations


class Migration(migrations.Migration):
    """
    PackingPieceConsumption.issued_piece -> issued_material — the shared
    services/_shared.py draw_fifo/return_fifo helpers hardcode the kwarg
    name `issued_material` for every FIFO consumption model in this app
    (RecipeMaterialConsumption/CuttingMaterialConsumption both already use
    it); this field was misnamed at 0010 and caught by a service-layer
    smoke test before any real data ever used it.
    """

    dependencies = [
        ("production", "0011_wipproduct_code_not_null"),
    ]

    operations = [
        migrations.RenameField(
            model_name="packingpiececonsumption",
            old_name="issued_piece",
            new_name="issued_material",
        ),
    ]
