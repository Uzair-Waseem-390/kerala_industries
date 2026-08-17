from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from purchases.models import Category, Product, Shelf
from users.models import User

from .models import ProductRate, ProductRateHistory
from .selectors import get_price_at_date
from .services import create_rate, update_rate
from .views import ProductRateHistoryView, ProductRateListCreateView


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
        self.category = Category.objects.create(name="Cat A")
        self.shelf = Shelf.objects.create(name="Shelf A")

    def make_product(self, code="P001", name="Product 1"):
        return Product.objects.create(
            name=name, code=code, category=self.category,
        )


class RateServiceTests(RatesTestBase):
    def test_create_rate_logs_initial_history(self):
        product = self.make_product()
        rate = create_rate(product_id=product.id, selling_price=Decimal("100"), user=self.admin)
        self.assertEqual(rate.selling_price, Decimal("100"))
        self.assertEqual(ProductRateHistory.objects.filter(product=product).count(), 1)

    def test_update_rate_appends_history(self):
        product = self.make_product()
        rate = create_rate(product_id=product.id, selling_price=Decimal("100"), user=self.admin)
        update_rate(pk=rate.pk, selling_price=Decimal("150"), user=self.admin)
        rate.refresh_from_db()
        self.assertEqual(rate.selling_price, Decimal("150"))
        self.assertEqual(ProductRateHistory.objects.filter(product=product).count(), 2)

    def test_update_rolls_back_price_if_history_write_fails(self):
        # Billing snapshots prices FROM history — a price change without its
        # history row must be impossible.
        product = self.make_product()
        rate = create_rate(product_id=product.id, selling_price=Decimal("100"), user=self.admin)

        with patch("rates.services._log_rate_history", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                update_rate(pk=rate.pk, selling_price=Decimal("999"), user=self.admin)

        rate.refresh_from_db()
        self.assertEqual(rate.selling_price, Decimal("100"))
        self.assertEqual(ProductRateHistory.objects.filter(product=product).count(), 1)

    def test_create_rolls_back_rate_if_history_write_fails(self):
        product = self.make_product()
        with patch("rates.services._log_rate_history", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                create_rate(product_id=product.id, selling_price=Decimal("100"), user=self.admin)
        self.assertFalse(ProductRate.objects.filter(product=product).exists())


class RateCreateEndpointTests(RatesTestBase):
    def post_rate(self, product, user, price="100.00"):
        request = self.factory.post(
            "/rates/", {"product_id": product.id, "selling_price": price}, format="json",
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
        create_rate(product_id=product.id, selling_price=Decimal("100"), user=self.admin)

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
        create_rate(product_id=p1.id, selling_price=Decimal("100"), user=self.admin)
        baseline = self.count_queries()

        for i in range(4):
            p = self.make_product(f"P10{i}", f"Product 10{i}")
            create_rate(product_id=p.id, selling_price=Decimal("100"), user=self.admin)
        grown = self.count_queries()
        self.assertEqual(baseline, grown)


class PriceAtDateTests(RatesTestBase):
    def test_returns_price_effective_at_each_point_in_time(self):
        product = self.make_product()
        rate = create_rate(product_id=product.id, selling_price=Decimal("100"), user=self.admin)

        # Backdate the initial entry so there's a clear gap between changes.
        first_entry = ProductRateHistory.objects.get(product=product)
        ten_days_ago = timezone.now() - timedelta(days=10)
        ProductRateHistory.objects.filter(pk=first_entry.pk).update(changed_at=ten_days_ago)

        update_rate(pk=rate.pk, selling_price=Decimal("150"), user=self.admin)

        before_any = timezone.now() - timedelta(days=20)
        between    = timezone.now() - timedelta(days=5)
        now        = timezone.now()

        self.assertIsNone(get_price_at_date(product.id, before_any))
        self.assertEqual(get_price_at_date(product.id, between).selling_price, Decimal("100"))
        self.assertEqual(get_price_at_date(product.id, now).selling_price, Decimal("150"))


class RateHistoryEndpointTests(RatesTestBase):
    def test_history_is_newest_first_with_product_info(self):
        product = self.make_product()
        rate = create_rate(product_id=product.id, selling_price=Decimal("100"), user=self.admin)
        update_rate(pk=rate.pk, selling_price=Decimal("150"), user=self.admin)

        request = self.factory.get(f"/rates/history/{product.id}/")
        force_authenticate(request, user=make_normal_user())
        response = ProductRateHistoryView.as_view()(request, product_id=product.id)

        self.assertEqual(response.status_code, 200)
        prices = [r["selling_price"] for r in response.data["results"]]
        self.assertEqual(prices, ["150.0000", "100.0000"])
        self.assertEqual(response.data["results"][0]["product_code"], "P001")
