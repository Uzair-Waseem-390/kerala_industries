from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from purchases.models import Family, Product, Shelf
from users.models import User

from .models import ProductRate, ProductRateHistory
from .selectors import get_price_at_date
from .services import create_rate, update_rate
from .views import ProductCostView, ProductRateHistoryView, ProductRateListCreateView


def make_admin(email="admin@example.com"):
    return User.objects.create_user(
        email=email, password="Adm1n-secret!", first_name="Admin",
        last_name="User", is_staff=True,
    )


def make_normal_user(email="normal@example.com"):
    return User.objects.create_user(
        email=email, password="N0rmal-secret!", first_name="Normal", last_name="User",
    )


class RatesTestBase(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = make_admin()
        self.shelf = Shelf.objects.create(name="Shelf A")
        # rates now only allows pricing RM products in the Cartons line (see
        # purchases.selectors.is_cartons_product) — every product these
        # tests price must be a variant of the Cartons anchor.
        from purchases.models import CARTONS_PRODUCT_CODE
        self.cartons_anchor, _ = Product.objects.get_or_create(
            code=CARTONS_PRODUCT_CODE,
            defaults={"name": "Cartons", "family": Family.objects.get(name="Raw Material")},
        )

    def make_product(self, code="P001", name="Product 1"):
        return Product.objects.create(
            name=name, code=code, family=Family.objects.get(name="Raw Material"),
            base_product=self.cartons_anchor,
        )


class RateServiceTests(RatesTestBase):
    def test_create_rate_logs_initial_history(self):
        product = self.make_product()
        rate = create_rate(rm_product_id=product.id, selling_price=Decimal("100"), user=self.admin)
        self.assertEqual(rate.selling_price, Decimal("100"))
        self.assertEqual(ProductRateHistory.objects.filter(rm_product=product).count(), 1)

    def test_update_rate_appends_history(self):
        product = self.make_product()
        rate = create_rate(rm_product_id=product.id, selling_price=Decimal("100"), user=self.admin)
        update_rate(pk=rate.pk, selling_price=Decimal("150"), user=self.admin)
        rate.refresh_from_db()
        self.assertEqual(rate.selling_price, Decimal("150"))
        self.assertEqual(ProductRateHistory.objects.filter(rm_product=product).count(), 2)

    def test_update_rolls_back_price_if_history_write_fails(self):
        # Billing snapshots prices FROM history — a price change without its
        # history row must be impossible.
        product = self.make_product()
        rate = create_rate(rm_product_id=product.id, selling_price=Decimal("100"), user=self.admin)

        with patch("rates.services._log_rate_history", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                update_rate(pk=rate.pk, selling_price=Decimal("999"), user=self.admin)

        rate.refresh_from_db()
        self.assertEqual(rate.selling_price, Decimal("100"))
        self.assertEqual(ProductRateHistory.objects.filter(rm_product=product).count(), 1)

    def test_create_rolls_back_rate_if_history_write_fails(self):
        product = self.make_product()
        with patch("rates.services._log_rate_history", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                create_rate(rm_product_id=product.id, selling_price=Decimal("100"), user=self.admin)
        self.assertFalse(ProductRate.objects.filter(rm_product=product).exists())


class RateCreateEndpointTests(RatesTestBase):
    def post_rate(self, product, user, price="100.00"):
        request = self.factory.post(
            "/rates/", {"rm_product_id": product.id, "selling_price": price}, format="json",
        )
        force_authenticate(request, user=user)
        return ProductRateListCreateView.as_view()(request)

    def test_create_and_duplicate_return_400(self):
        product = self.make_product()
        self.assertEqual(self.post_rate(product, self.admin).status_code, 201)
        self.assertEqual(self.post_rate(product, self.admin).status_code, 400)

    def test_duplicate_race_returns_400_not_500(self):
        # Bypass the exists() pre-check to simulate two concurrent creates —
        # the OneToOne constraint fires and must surface as a clean 400.
        product = self.make_product()
        create_rate(rm_product_id=product.id, selling_price=Decimal("100"), user=self.admin)

        with patch(
            "rates.services.ProductRate.objects.filter",
            return_value=ProductRate.objects.none(),
        ):
            response = self.post_rate(product, self.admin)
        self.assertEqual(response.status_code, 400)
        self.assertIn("product", response.data)

    def test_normal_user_cannot_create_rate(self):
        product = self.make_product()
        response = self.post_rate(product, make_normal_user())
        self.assertEqual(response.status_code, 403)


class RateListQueryCountTests(RatesTestBase):
    def count_queries(self):
        request = self.factory.get("/rates/")
        force_authenticate(request, user=self.admin)
        with CaptureQueriesContext(connection) as ctx:
            response = ProductRateListCreateView.as_view()(request)
            response.render()
        self.assertEqual(response.status_code, 200)
        return len(ctx.captured_queries)

    def test_rate_list_query_count_is_flat(self):
        p1 = self.make_product("P001")
        create_rate(rm_product_id=p1.id, selling_price=Decimal("100"), user=self.admin)
        baseline = self.count_queries()

        for i in range(4):
            p = self.make_product(f"P10{i}", f"Product 10{i}")
            create_rate(rm_product_id=p.id, selling_price=Decimal("100"), user=self.admin)
        grown = self.count_queries()
        self.assertEqual(baseline, grown)


class PriceAtDateTests(RatesTestBase):
    def test_returns_price_effective_at_each_point_in_time(self):
        product = self.make_product()
        rate = create_rate(rm_product_id=product.id, selling_price=Decimal("100"), user=self.admin)

        # Backdate the initial entry so there's a clear gap between changes.
        first_entry = ProductRateHistory.objects.get(rm_product=product)
        ten_days_ago = timezone.now() - timedelta(days=10)
        ProductRateHistory.objects.filter(pk=first_entry.pk).update(changed_at=ten_days_ago)

        update_rate(pk=rate.pk, selling_price=Decimal("150"), user=self.admin)

        before_any = timezone.now() - timedelta(days=20)
        between    = timezone.now() - timedelta(days=5)
        now        = timezone.now()

        self.assertIsNone(get_price_at_date(rm_product_id=product.id, at=before_any))
        self.assertEqual(get_price_at_date(rm_product_id=product.id, at=between).selling_price, Decimal("100"))
        self.assertEqual(get_price_at_date(rm_product_id=product.id, at=now).selling_price, Decimal("150"))


class ProductCostEndpointTests(RatesTestBase):
    """
    GET /rates/cost/<product_type>/<product_id>/ — the COGS figure shown in
    RateFormModal while setting/editing a price (reports.selectors
    .get_product_avg_unit_cost). Admin/superuser only — stricter than the
    price-history endpoint above.
    """

    def make_stocked_product(self, code="P001", quantity=10, unit_price="50"):
        from purchases.services import (
            confirm_purchase_order, create_purchase_order, create_supplier,
            set_purchase_item_shelf_allocations,
        )

        product = self.make_product(code=code)
        supplier = create_supplier(name="Test Supplier", code=f"SUP-{code}", user=self.admin)
        order = create_purchase_order(
            supplier_id=supplier.id,
            items=[{"product_id": product.id, "quantity": quantity, "unit_price": Decimal(unit_price)}],
            user=self.admin,
        )
        for item in order.items.all():
            set_purchase_item_shelf_allocations(
                purchase_item_id=item.id,
                allocations=[{"shelf_id": self.shelf.id, "quantity": item.quantity}],
                user=self.admin,
            )
        confirm_purchase_order(order_id=order.id, user=self.admin)
        return product

    def test_returns_avg_unit_cost_for_stocked_product(self):
        product = self.make_stocked_product(quantity=10, unit_price="50")

        request = self.factory.get(f"/rates/cost/rm/{product.id}/")
        force_authenticate(request, user=self.admin)
        response = ProductCostView.as_view()(request, product_type="rm", product_id=product.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["avg_unit_cost"], "50.0000")
        self.assertEqual(response.data["quantity_on_hand"], "10.0000")
        self.assertTrue(response.data["has_stock"])

    def test_zero_stock_product_reports_no_cost_data(self):
        product = self.make_product(code="P002")

        request = self.factory.get(f"/rates/cost/rm/{product.id}/")
        force_authenticate(request, user=self.admin)
        response = ProductCostView.as_view()(request, product_type="rm", product_id=product.id)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["has_stock"])
        self.assertEqual(response.data["avg_unit_cost"], "0.0000")

    def test_normal_user_cannot_view_cost(self):
        product = self.make_stocked_product(code="P003")

        request = self.factory.get(f"/rates/cost/rm/{product.id}/")
        force_authenticate(request, user=make_normal_user())
        response = ProductCostView.as_view()(request, product_type="rm", product_id=product.id)

        self.assertEqual(response.status_code, 403)

    def test_unknown_product_returns_404(self):
        request = self.factory.get("/rates/cost/rm/999999/")
        force_authenticate(request, user=self.admin)
        response = ProductCostView.as_view()(request, product_type="rm", product_id=999999)

        self.assertEqual(response.status_code, 404)


class RateHistoryEndpointTests(RatesTestBase):
    def test_history_is_newest_first_with_product_info(self):
        product = self.make_product()
        rate = create_rate(rm_product_id=product.id, selling_price=Decimal("100"), user=self.admin)
        update_rate(pk=rate.pk, selling_price=Decimal("150"), user=self.admin)

        request = self.factory.get(f"/rates/history/{product.id}/")
        force_authenticate(request, user=make_normal_user())
        response = ProductRateHistoryView.as_view()(request, product_type="rm", product_id=product.id)

        self.assertEqual(response.status_code, 200)
        prices = [r["selling_price"] for r in response.data["results"]]
        self.assertEqual(prices, ["150.0000", "100.0000"])
        self.assertEqual(response.data["results"][0]["product_code"], "P001")
