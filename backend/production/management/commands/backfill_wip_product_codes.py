from django.core.management.base import BaseCommand
from django.db import transaction

from production.models import WipProduct
from production.services._shared import next_wip_product_code


class Command(BaseCommand):
    """
    One-time backfill for WipProduct rows created before the `code` field
    existed. Assigns a sequential WIP-<year>-#### code (same generator new
    rows use) to every row still missing one, oldest-created first.

    Idempotent — rows that already have a code are skipped, so running this
    twice never double-assigns or reshuffles existing codes.
    """

    help = "Assign a sequential auto-generated code to every WipProduct row missing one."

    def handle(self, *args, **options):
        missing = list(WipProduct.all_objects.filter(code__isnull=True).order_by("created_at", "id"))
        if not missing:
            self.stdout.write(self.style.SUCCESS("No WipProduct rows are missing a code."))
            return

        with transaction.atomic():
            for product in missing:
                product.code = next_wip_product_code()
                product.save(update_fields=["code"])

        self.stdout.write(self.style.SUCCESS(f"Assigned codes to {len(missing)} WipProduct row(s)."))
