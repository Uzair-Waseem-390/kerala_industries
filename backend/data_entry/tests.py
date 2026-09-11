from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from rest_framework.exceptions import ValidationError

from billing.services import create_customer
from purchases.services import create_supplier
from users.models import User

from .models import CustomerOpeningBalance, SupplierOpeningBalance
from .services import create_customer_opening_balance, create_supplier_opening_balance


def make_admin(email="admin@example.com"):
    return User.objects.create_user(
        email=email, password="Adm1n-secret!", first_name="Admin",
        last_name="User", is_staff=True, is_superuser=True,
    )


class OpeningBalanceDuplicateGuardTests(TestCase):
    """
    Both opening-balance creates check-then-act on .exists() before writing,
    but the OneToOneField already makes a true duplicate impossible at the
    DB level. These tests force the .exists() check to (falsely) pass, to
    prove the IntegrityError fallback converts the DB's rejection into the
    same friendly ValidationError instead of an unhandled 500 — the actual
    race this guards against.
    """

    def setUp(self):
        self.admin = make_admin()

    def test_supplier_opening_balance_race_returns_validation_error(self):
        supplier = create_supplier(name="Ali Traders", code="ALI", user=self.admin)
        create_supplier_opening_balance(supplier_id=supplier.id, amount=Decimal("500"), user=self.admin)
        self.assertEqual(SupplierOpeningBalance.objects.filter(supplier=supplier).count(), 1)

        with patch(
            "django.db.models.query.QuerySet.exists", return_value=False,
        ):
            with self.assertRaises(ValidationError) as ctx:
                create_supplier_opening_balance(supplier_id=supplier.id, amount=Decimal("200"), user=self.admin)
        self.assertIn("supplier", ctx.exception.detail)

        # No corruption: still exactly one row, original amount untouched.
        self.assertEqual(SupplierOpeningBalance.objects.filter(supplier=supplier).count(), 1)
        self.assertEqual(SupplierOpeningBalance.objects.get(supplier=supplier).amount, Decimal("500.0000"))

    def test_customer_opening_balance_race_returns_validation_error(self):
        customer = create_customer(name="Big Mart", code="BM", address="Main St", user=self.admin)
        create_customer_opening_balance(customer_id=customer.id, amount=Decimal("300"), user=self.admin)
        self.assertEqual(CustomerOpeningBalance.objects.filter(customer=customer).count(), 1)

        with patch(
            "django.db.models.query.QuerySet.exists", return_value=False,
        ):
            with self.assertRaises(ValidationError) as ctx:
                create_customer_opening_balance(customer_id=customer.id, amount=Decimal("100"), user=self.admin)
        self.assertIn("customer", ctx.exception.detail)

        self.assertEqual(CustomerOpeningBalance.objects.filter(customer=customer).count(), 1)
        self.assertEqual(CustomerOpeningBalance.objects.get(customer=customer).amount, Decimal("300.0000"))

    def test_normal_duplicate_still_blocked_by_exists_check(self):
        supplier = create_supplier(name="Karachi Metals", code="KM", user=self.admin)
        create_supplier_opening_balance(supplier_id=supplier.id, amount=Decimal("100"), user=self.admin)

        with self.assertRaises(ValidationError):
            create_supplier_opening_balance(supplier_id=supplier.id, amount=Decimal("50"), user=self.admin)


class OpeningWipFgStockTests(TestCase):
    """
    Opening WIP/FG stock (2026-09) — data_entry's WIP/FG bootstrap. Real
    production.Recipe (is_data_entry=True) + RecipeBreakdownItem/
    CuttingBreakdownItem/PackingOutputItem rows underneath, exactly like
    real production output, but excluded from the normal Recipes list.
    """

    def setUp(self):
        self.admin = make_admin()
        from purchases.models import Shelf
        self.shelf = Shelf.objects.create(name="Shelf A", created_by=self.admin, updated_by=self.admin)
        self.binding, self.yard, self.length_mm = self._make_lookups()

    def _make_lookups(self, suffix=""):
        from production.models import RewoundCoreBinding, RewoundCoreLengthMm, RewoundCoreYard
        binding = RewoundCoreBinding.objects.create(
            value=f"Test Binding{suffix}", created_by=self.admin, updated_by=self.admin,
        )
        yard, _ = RewoundCoreYard.objects.get_or_create(
            value=Decimal("50"), defaults={"created_by": self.admin, "updated_by": self.admin},
        )
        length_mm, _ = RewoundCoreLengthMm.objects.get_or_create(
            value=Decimal("100"), defaults={"created_by": self.admin, "updated_by": self.admin},
        )
        return binding, yard, length_mm

    def test_wip_core_opening_stock_creates_product_and_inventory(self):
        from production.services.opening_stock import create_opening_wip_stock
        from production.models import WipProduct
        from inventory.models import WipInventory, WipShelfStock

        recipe = create_opening_wip_stock(items=[{
            "binding_id": self.binding.id, "yard_id": self.yard.id, "length_mm_id": self.length_mm.id,
            "stage": WipProduct.Stage.REWINDING, "quantity": 10, "unit_cost": 25, "shelf_id": self.shelf.id,
        }], user=self.admin)

        self.assertTrue(recipe.is_data_entry)
        self.assertEqual(recipe.status, "finished")
        wip = WipProduct.objects.get(
            binding=self.binding, yard=self.yard, length_mm=self.length_mm, stage=WipProduct.Stage.REWINDING,
        )
        self.assertEqual(WipInventory.objects.get(product=wip).quantity, Decimal("10"))
        self.assertEqual(WipShelfStock.objects.get(product=wip, shelf=self.shelf).quantity, Decimal("10"))

    def test_wip_opening_stock_reuses_same_product_on_second_call(self):
        from production.services.opening_stock import create_opening_wip_stock
        from production.models import WipProduct
        from inventory.models import WipInventory

        item = {
            "binding_id": self.binding.id, "yard_id": self.yard.id, "length_mm_id": self.length_mm.id,
            "stage": WipProduct.Stage.REWINDING, "quantity": 10, "unit_cost": 25, "shelf_id": self.shelf.id,
        }
        create_opening_wip_stock(items=[item], user=self.admin)
        create_opening_wip_stock(items=[{**item, "quantity": 5, "unit_cost": 30}], user=self.admin)

        wip_qs = WipProduct.objects.filter(binding=self.binding, yard=self.yard, length_mm=self.length_mm)
        self.assertEqual(wip_qs.count(), 1)
        self.assertEqual(WipInventory.objects.get(product=wip_qs.first()).quantity, Decimal("15"))

    def test_fg_opening_stock_with_multiple_items_creates_one_recipe_each(self):
        """Regression: PackingOutputItem.recipe is a OneToOneField — a
        shared recipe across multiple FG items would violate it."""
        from production.services.opening_stock import create_opening_fg_stock
        from production.models import PackingOutputItem

        binding2, yard2, length_mm2 = self._make_lookups(suffix="2")
        recipes = create_opening_fg_stock(items=[
            {"binding_id": self.binding.id, "yard_id": self.yard.id, "length_mm_id": self.length_mm.id,
             "quantity": 5, "unit_cost": 10, "shelf_id": self.shelf.id},
            {"binding_id": binding2.id, "yard_id": yard2.id, "length_mm_id": length_mm2.id,
             "quantity": 7, "unit_cost": 20, "shelf_id": self.shelf.id},
        ], user=self.admin)

        self.assertEqual(len(recipes), 2)
        self.assertEqual(len({r.id for r in recipes}), 2)
        for recipe in recipes:
            self.assertTrue(recipe.is_data_entry)
            self.assertTrue(PackingOutputItem.objects.filter(recipe=recipe).exists())

    def test_opening_stock_recipes_excluded_from_normal_recipes_list(self):
        from production.services.opening_stock import create_opening_wip_stock, create_opening_fg_stock
        from production.selectors.rewinding import get_all_recipes
        from production.models import WipProduct

        wip_recipe = create_opening_wip_stock(items=[{
            "binding_id": self.binding.id, "yard_id": self.yard.id, "length_mm_id": self.length_mm.id,
            "stage": WipProduct.Stage.REWINDING, "quantity": 10, "unit_cost": 25, "shelf_id": self.shelf.id,
        }], user=self.admin)
        binding2, yard2, length_mm2 = self._make_lookups(suffix="2")
        fg_recipes = create_opening_fg_stock(items=[{
            "binding_id": binding2.id, "yard_id": yard2.id, "length_mm_id": length_mm2.id,
            "quantity": 5, "unit_cost": 10, "shelf_id": self.shelf.id,
        }], user=self.admin)

        listed_ids = set(get_all_recipes().values_list("id", flat=True))
        self.assertNotIn(wip_recipe.id, listed_ids)
        self.assertNotIn(fg_recipes[0].id, listed_ids)

    def test_opening_stock_recipe_has_zero_labor_overhead_pool(self):
        from production.services.opening_stock import create_opening_wip_stock
        from production.services._shared import compute_labor_overhead_pool
        from production.models import WipProduct

        recipe = create_opening_wip_stock(items=[{
            "binding_id": self.binding.id, "yard_id": self.yard.id, "length_mm_id": self.length_mm.id,
            "stage": WipProduct.Stage.REWINDING, "quantity": 10, "unit_cost": 25, "shelf_id": self.shelf.id,
        }], user=self.admin)
        self.assertEqual(compute_labor_overhead_pool(recipe), Decimal("0"))

    def test_wip_opening_stock_visible_in_inventory_valuation(self):
        from production.services.opening_stock import create_opening_wip_stock
        from production.models import WipProduct
        from reports.selectors import get_inventory_valuation_report_data

        create_opening_wip_stock(items=[{
            "binding_id": self.binding.id, "yard_id": self.yard.id, "length_mm_id": self.length_mm.id,
            "stage": WipProduct.Stage.REWINDING, "quantity": 10, "unit_cost": 25, "shelf_id": self.shelf.id,
        }], user=self.admin)

        rows = get_inventory_valuation_report_data(search="Test Binding")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["type"], "wip_core")
        self.assertEqual(rows[0]["total_value"], Decimal("250"))
