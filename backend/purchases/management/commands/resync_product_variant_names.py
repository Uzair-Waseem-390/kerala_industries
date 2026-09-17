from django.core.management.base import BaseCommand

from purchases.models import Product
from purchases.services import _VARIANT_NAME_SELECT_RELATED, _rebuild_variant_name


class Command(BaseCommand):
    """
    One-time backfill for variants whose name already drifted stale BEFORE
    update_jumbo_name/update_core_name/update_core_length/
    update_core_thickness/update_packing_size/update_carton_size started
    cascade-renaming their existing Product variants (fixed 2026-09-18) —
    every rename before that fix left every already-created variant's name
    frozen at its old value. Safe to re-run any time (idempotent: only
    writes rows whose computed name actually differs from what's stored).

    Scans every non-anchor Product (base_product is not null — the 4
    anchor rows have no attribute FKs to drift) exactly once; O(variant
    count), not O(variant count x lookups), since each row's own current
    FK values are read via select_related, no per-row extra query.
    """

    help = "Resyncs every Product variant's name from its current Jumbo/Core/Packing/Carton attribute values."

    def handle(self, *args, **options):
        products = (
            Product.all_objects.filter(base_product__isnull=False)
            .select_related(*_VARIANT_NAME_SELECT_RELATED)
        )
        updated = 0
        for product in products:
            new_name = _rebuild_variant_name(product)
            if new_name != product.name:
                old_name = product.name
                product.name = new_name
                product.save(update_fields=["name", "updated_at"])
                updated += 1
                self.stdout.write(f"  {product.code}: '{old_name}' -> '{new_name}'")

        self.stdout.write(self.style.SUCCESS(f"Resynced {updated} product variant name(s)."))
