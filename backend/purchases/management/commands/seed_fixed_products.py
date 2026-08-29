from django.core.management.base import BaseCommand
from django.db import transaction

from purchases.models import (
    CARTONS_PRODUCT_CODE, CORES_PRODUCT_CODE, Family, JUMBO_PRODUCT_CODE,
    PACKING_PRODUCT_CODE, Product,
)
from purchases.services import create_product

# The ONLY 4 products this system will ever have. Product create/edit/delete
# are no longer exposed via the API (see purchases/views.py — ProductListView/
# ProductRetrieveView are read-only now) — this command is the sole place new
# Product rows get created, reusing the existing create_product() service so
# its side effects (queueing the product into rates' unpriced list, keeping
# inventory stats in sync) fire exactly as they always have. Codes are the
# single source of truth in purchases.models — every attribute-bearing
# variant traces back to one of these 4 rows via Product.base_product.
FIXED_PRODUCTS = [
    {"code": JUMBO_PRODUCT_CODE, "name": "Jumbo"},
    {"code": CORES_PRODUCT_CODE, "name": "Cores"},
    {"code": PACKING_PRODUCT_CODE, "name": "Packing"},
    {"code": CARTONS_PRODUCT_CODE, "name": "Cartons"},
]


class Command(BaseCommand):
    """
    Seeds the 4 fixed products: Jumbo, Cores, Packing, Cartons.
    Safe to re-run — skips any code that already exists (including
    soft-deleted rows, to avoid a duplicate-code collision on retry)
    instead of erroring.
    """

    help = "Seeds the 4 fixed products (Jumbo, Cores, Packing, Cartons). Safe to re-run."

    @transaction.atomic
    def handle(self, *args, **options):
        # No request.user in a management command context — None is valid
        # (AuditMixin's created_by/updated_by are SET_NULL), same convention
        # as data_entry.create_system_supplier.
        user = None
        raw_material = Family.objects.get(name="Raw Material")

        for spec in FIXED_PRODUCTS:
            if Product.all_objects.filter(code=spec["code"]).exists():
                self.stdout.write(f"'{spec['name']}' ({spec['code']}) already exists — skipped.")
                continue
            product = create_product(
                name=spec["name"], code=spec["code"], family_id=raw_material.id, user=user,
            )
            self.stdout.write(self.style.SUCCESS(
                f"Created '{product.name}' ({product.code}), id={product.pk}."
            ))
