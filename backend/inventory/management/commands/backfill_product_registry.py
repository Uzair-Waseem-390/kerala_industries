from django.core.management.base import BaseCommand
from django.db import transaction

from inventory.models import ProductRegistryEntry
from production.models import FgProduct, WipProduct
from purchases.models import Product


class Command(BaseCommand):
    """
    One-time backfill for ProductRegistryEntry — writes a registry row for
    every existing RM variant / WipProduct / FgProduct that predates the
    registry (see inventory.services.create_registry_entry, which every new
    product creation path calls going forward). Uses each product's
    `all_objects` manager (not the soft-delete-filtered default) so a
    currently-soft-deleted product still gets an entry — read-time
    filtering (selectors.get_all_registry_products) already excludes
    soft-deleted products by joining is_deleted live, so a restored product
    needs its registry row to already exist, not get created again.

    Idempotent — get_or_create by the same OneToOneField the registry's
    uniqueness already enforces, so running this twice never duplicates.
    """

    help = "Backfill ProductRegistryEntry for existing RM/WIP/FG products created before the registry existed."

    def handle(self, *args, **options):
        rm_created = wip_created = fg_created = 0

        with transaction.atomic():
            for product in Product.all_objects.filter(base_product__isnull=False).select_related("family"):
                _, created = ProductRegistryEntry.objects.get_or_create(
                    rm_product=product,
                    defaults={
                        "type": ProductRegistryEntry.Type.RAW_MATERIAL,
                        "name": product.name, "code": product.code,
                        "category": product.family.name if product.family_id else None,
                    },
                )
                rm_created += created

            for wip_product in WipProduct.all_objects.all():
                wip_type = (
                    ProductRegistryEntry.Type.WIP_PIECE if wip_product.stage == WipProduct.Stage.CUTTING
                    else ProductRegistryEntry.Type.WIP_CORE
                )
                _, created = ProductRegistryEntry.objects.get_or_create(
                    wip_product=wip_product,
                    defaults={
                        "type": wip_type, "name": wip_product.name, "code": wip_product.code, "category": "WIP",
                    },
                )
                wip_created += created

            for fg_product in FgProduct.all_objects.all():
                _, created = ProductRegistryEntry.objects.get_or_create(
                    fg_product=fg_product,
                    defaults={
                        "type": ProductRegistryEntry.Type.FINISHED_GOODS, "name": fg_product.name,
                        "code": fg_product.code, "category": "Finished Goods",
                    },
                )
                fg_created += created

        self.stdout.write(self.style.SUCCESS(
            f"ProductRegistryEntry backfilled — RM: {rm_created} created, "
            f"WIP: {wip_created} created, FG: {fg_created} created."
        ))
