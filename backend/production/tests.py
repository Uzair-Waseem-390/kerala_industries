from decimal import Decimal

from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from inventory.models import FgInventory, FgInventoryStatsFlow, FgShelfStock, WipInventoryStatsFlow
from purchases.models import Family, Shelf, Supplier
from purchases.services import (
    confirm_purchase_order, create_core_length, create_core_purchase,
    create_jumbo_purchase, create_packing_purchase, create_packing_size, create_supplier,
    set_purchase_item_shelf_allocations,
)
from users.models import User

from .models import CuttingBreakdownItem, FgProduct, PackingIssuedMaterial, PackingIssuedPiece, Recipe, WipProduct
from .selectors import get_packing_recipe_by_id
from .services import (
    add_breakdown_item, add_cutting_breakdown_item, create_cutting_recipe, create_packing_recipe,
    create_recipe, finish_cutting_recipe, finish_packing_recipe, finish_recipe,
    issue_cutting_material, issue_material, issue_packing_material, issue_packing_piece,
    update_packing_issued_material, update_packing_issued_piece, update_recipe_description,
)
from .views import PackingRecipeListCreateView, PackingRecipeRetrieveView


def make_admin(email="admin@example.com"):
    return User.objects.create_user(
        email=email, password="Adm1n-secret!", first_name="Admin", last_name="User", is_staff=True,
    )


def make_normal_user(email="normal@example.com"):
    return User.objects.create_user(
        email=email, password="N0rmal-secret!", first_name="Normal", last_name="User",
    )


class PackingRecipeTestBase(TestCase):
    """
    Builds the full RM -> WIP (Rewinding) -> WIP (Cutting) chain via the
    real service functions, exactly the way the app itself does, so
    Packing's tests exercise real upstream data (a finished Cutting batch)
    rather than hand-inserted rows.
    """

    def setUp(self):
        call_command("seed_fixed_products")
        self.factory = APIRequestFactory()
        self.admin = make_admin()
        self.shelf = Shelf.objects.create(name="Shelf A")
        self.supplier = create_supplier(name="Ali Traders", code="ALI", user=self.admin)

        # --- RM purchases: Jumbo, Cores, Packing Material ---
        core_length = create_core_length(value="1", user=self.admin)  # 1 inch -> 25.4mm
        packing_size = create_packing_size(value="5.0", user=self.admin)

        from purchases.services import create_jumbo_name
        jumbo_name = create_jumbo_name(value="binding 210", user=self.admin)

        jumbo_order = create_jumbo_purchase(
            supplier_id=self.supplier.id, jumbo_name_id=jumbo_name.id,
            rate_per_kg=Decimal("50"), weight_kg=Decimal("100"), expected_length_m=Decimal("100"),
            user=self.admin,
        )
        cores_order = create_core_purchase(
            supplier_id=self.supplier.id, quantity=Decimal("20"), unit_price=Decimal("10"),
            core_length_id=core_length.id, user=self.admin,
        )
        packing_order = create_packing_purchase(
            supplier_id=self.supplier.id, packing_size_id=packing_size.id,
            rate_per_kg=Decimal("100"), weight_kg=Decimal("10"), user=self.admin,
        )
        for order in (jumbo_order, cores_order, packing_order):
            for item in order.items.all():
                set_purchase_item_shelf_allocations(
                    purchase_item_id=item.id,
                    allocations=[{"shelf_id": self.shelf.id, "quantity": item.quantity}],
                    user=self.admin,
                )
            confirm_purchase_order(order_id=order.id, user=self.admin)

        self.jumbo_product = jumbo_order.items.first().product
        self.cores_product = cores_order.items.first().product
        self.packing_material = packing_order.items.first().product

        # --- Rewinding: issue Jumbo + Cores, breakdown into whole cores, finish ---
        rewinding = create_recipe(name="Rewinding Test", user=self.admin)
        issue_material(
            recipe_id=rewinding.id, kind="jumbo", product_id=self.jumbo_product.id,
            quantity=self.jumbo_product.inventory.quantity,
            shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": self.jumbo_product.inventory.quantity}],
            user=self.admin,
        )
        issue_material(
            recipe_id=rewinding.id, kind="cores", product_id=self.cores_product.id,
            quantity=Decimal("20"),
            shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("20")}],
            user=self.admin,
        )
        add_breakdown_item(
            recipe_id=rewinding.id, yard_value=Decimal("100"), quantity=Decimal("10"),
            shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("10")}],
            user=self.admin,
        )
        update_recipe_description(recipe_id=rewinding.id, description="Rewinding smoke", user=self.admin)
        finish_recipe(recipe_id=rewinding.id, user=self.admin)

        self.whole_core = WipProduct.objects.get(stage=WipProduct.Stage.REWINDING)

        # --- Cutting: issue the whole core, breakdown into pieces (no waste), finish ---
        cutting = create_cutting_recipe(name="Cutting Test", user=self.admin)
        issue_cutting_material(
            recipe_id=cutting.id, wip_product_id=self.whole_core.id, quantity=Decimal("10"),
            shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("10")}],
            user=self.admin,
        )
        add_cutting_breakdown_item(
            recipe_id=cutting.id, length_mm=self.whole_core.length_mm.value, quantity=Decimal("10"),
            shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("10")}],
            user=self.admin,
        )
        update_recipe_description(recipe_id=cutting.id, description="Cutting smoke", user=self.admin)
        finish_cutting_recipe(recipe_id=cutting.id, user=self.admin)

        self.piece = WipProduct.objects.get(stage=WipProduct.Stage.CUTTING)
        self.piece_batch = CuttingBreakdownItem.objects.get(wip_product=self.piece)


class PackingHappyPathTests(PackingRecipeTestBase):
    def test_full_packing_flow_costs_and_moves_stock_to_fg(self):
        recipe = create_packing_recipe(name="Packing Test", user=self.admin)

        issue_packing_piece(
            recipe_id=recipe.id, wip_product_id=self.piece.id, quantity=Decimal("4"),
            shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("4")}], user=self.admin,
        )
        issue_packing_material(
            recipe_id=recipe.id, product_id=self.packing_material.id, quantity=Decimal("0.4"),
            shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("0.4")}], user=self.admin,
        )
        update_recipe_description(recipe_id=recipe.id, description="Packing smoke", user=self.admin)

        finished = finish_packing_recipe(
            recipe_id=recipe.id,
            shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("4")}],
            user=self.admin,
        )

        self.assertEqual(finished.status, Recipe.Status.FINISHED)

        output = finished.packing_output_item
        fg_product = output.fg_product
        self.assertEqual(fg_product.name, self.piece.name)
        self.assertEqual(output.quantity, Decimal("4"))

        piece_unit_cost = self.piece_batch.unit_cost_snapshot
        packing_cost_per_piece = (Decimal("0.4") * Decimal("100")) / Decimal("4")  # 0.4kg @ 100/kg / 4 pieces
        expected_fg_cost = (piece_unit_cost + packing_cost_per_piece).quantize(Decimal("0.0001"))
        self.assertEqual(output.unit_cost_snapshot, expected_fg_cost)
        self.assertEqual(finished.cost_per_unit, expected_fg_cost)

        fg_inventory = FgInventory.objects.get(product=fg_product)
        self.assertEqual(fg_inventory.quantity, Decimal("4"))
        fg_shelf = FgShelfStock.objects.get(product=fg_product, shelf=self.shelf)
        self.assertEqual(fg_shelf.quantity, Decimal("4"))

        stats = FgInventoryStatsFlow.get_instance()
        self.assertEqual(stats.total_products, 1)
        self.assertEqual(stats.total_stock, Decimal("4"))

        self.piece.refresh_from_db()
        self.assertEqual(self.piece.inventory.quantity, Decimal("6"))  # 10 issued in - 4 packed
        self.packing_material.refresh_from_db()
        self.assertEqual(self.packing_material.inventory.quantity, Decimal("9.6"))

    def test_uneven_division_reconciles_via_single_combined_division(self):
        """
        Regression test for a rounding-order bug: computing piece_unit_cost
        and packing_cost_per_piece as two independently-quantized divisions
        and summing them can drift from a single division of the combined
        total. A single Cutting batch's per-piece cost is already an exact
        4dp value, so multiplying by N pieces and dividing back by the same
        N never itself needs rounding — the drift only shows up once the
        issued pieces are drawn across TWO batches at different costs (a
        real scenario: Packing issuing more pieces than one Cutting run
        produced). Adds a second batch directly (bypassing the recipe
        service layer, which isn't needed to set up this narrow numeric
        edge case) so the piece cost itself needs rounding too.
        """
        from django.utils import timezone as tz

        second_cutting_recipe = Recipe.objects.create(
            recipe_number="CUT-TEST-0002", recipe_type=Recipe.RecipeType.CUTTING,
            name="Second batch", status=Recipe.Status.FINISHED, finished_at=tz.now(),
            created_by=self.admin, updated_by=self.admin,
        )
        CuttingBreakdownItem.objects.create(
            recipe=second_cutting_recipe, wip_product=self.piece,
            length_mm=self.piece_batch.length_mm, quantity=Decimal("2"), remaining_quantity=Decimal("2"),
            unit_cost_snapshot=Decimal("100.0000"), created_by=self.admin, updated_by=self.admin,
        )
        # The FIFO batch alone isn't enough to issue against — WipInventory/
        # WipShelfStock (what issue_packing_piece's shelf-availability check
        # actually reads) need the extra 2 units too, same as a real Cutting
        # finish would have put away via sync_wip_inventory/apply_wip_shelf_allocations.
        from inventory.services import apply_wip_shelf_allocations, sync_wip_inventory
        from inventory.models import WipShelfStockMovement
        sync_wip_inventory(product=self.piece, quantity_delta=Decimal("2"), user=self.admin)
        apply_wip_shelf_allocations(
            product=self.piece, allocations=[{"shelf": self.shelf, "quantity": Decimal("2")}],
            sign=1, reason=WipShelfStockMovement.Reason.CUTTING_BREAKDOWN_PUTAWAY, user=self.admin,
        )

        recipe = create_packing_recipe(name="Packing Uneven", user=self.admin)
        # Draws all 10 remaining from the first (317.3090/unit) batch, then
        # 1 more from the second (100.0000/unit) batch — genuinely mixed cost.
        issue_packing_piece(
            recipe_id=recipe.id, wip_product_id=self.piece.id, quantity=Decimal("11"),
            shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("11")}], user=self.admin,
        )
        issue_packing_material(
            recipe_id=recipe.id, product_id=self.packing_material.id, quantity=Decimal("1.15"),
            shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("1.15")}], user=self.admin,
        )
        update_recipe_description(recipe_id=recipe.id, description="x", user=self.admin)
        finished = finish_packing_recipe(
            recipe_id=recipe.id,
            shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("11")}],
            user=self.admin,
        )

        piece_total_cost = Decimal("10") * self.piece_batch.unit_cost_snapshot + Decimal("1") * Decimal("100.0000")
        packing_total_cost = Decimal("1.15") * Decimal("100")
        combined_total = piece_total_cost + packing_total_cost
        expected_fg_cost = (combined_total / Decimal("11")).quantize(Decimal("0.0001"))

        output = finished.packing_output_item
        self.assertEqual(output.unit_cost_snapshot, expected_fg_cost)
        # The two-independent-divisions approach this replaced would have
        # given a different (wrong) result for these numbers — assert the
        # buggy formula and the fix actually diverge for this input,
        # otherwise this test wouldn't be exercising the bug at all.
        buggy_piece_unit_cost = (piece_total_cost / Decimal("11")).quantize(Decimal("0.0001"))
        buggy_packing_cost_per_piece = (packing_total_cost / Decimal("11")).quantize(Decimal("0.0001"))
        buggy_fg_cost = buggy_piece_unit_cost + buggy_packing_cost_per_piece
        self.assertNotEqual(buggy_fg_cost, expected_fg_cost)

    def test_packing_same_piece_twice_reuses_fg_product(self):
        """Packing the same piece identity in two separate recipes must reuse one FgProduct row, not duplicate it."""
        for i in range(2):
            recipe = create_packing_recipe(name=f"Packing {i}", user=self.admin)
            issue_packing_piece(
                recipe_id=recipe.id, wip_product_id=self.piece.id, quantity=Decimal("2"),
                shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("2")}], user=self.admin,
            )
            issue_packing_material(
                recipe_id=recipe.id, product_id=self.packing_material.id, quantity=Decimal("0.2"),
                shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("0.2")}], user=self.admin,
            )
            update_recipe_description(recipe_id=recipe.id, description="x", user=self.admin)
            finish_packing_recipe(
                recipe_id=recipe.id,
                shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("2")}],
                user=self.admin,
            )

        self.assertEqual(FgProduct.objects.filter(name=self.piece.name).count(), 1)
        fg_product = FgProduct.objects.get(name=self.piece.name)
        self.assertEqual(FgInventory.objects.get(product=fg_product).quantity, Decimal("4"))


class PackingValidationTests(PackingRecipeTestBase):
    def test_create_recipe_requires_name(self):
        with self.assertRaises(ValidationError):
            create_packing_recipe(name="   ", user=self.admin)

    def test_issue_piece_rejects_whole_core(self):
        recipe = create_packing_recipe(name="Packing", user=self.admin)
        with self.assertRaises(ValidationError):
            issue_packing_piece(
                recipe_id=recipe.id, wip_product_id=self.whole_core.id, quantity=Decimal("1"),
                shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("1")}], user=self.admin,
            )

    def test_issue_material_rejects_non_packing_product(self):
        recipe = create_packing_recipe(name="Packing", user=self.admin)
        with self.assertRaises(ValidationError):
            issue_packing_material(
                recipe_id=recipe.id, product_id=self.cores_product.id, quantity=Decimal("1"),
                shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("1")}], user=self.admin,
            )

    def test_issue_piece_twice_is_rejected(self):
        recipe = create_packing_recipe(name="Packing", user=self.admin)
        issue_packing_piece(
            recipe_id=recipe.id, wip_product_id=self.piece.id, quantity=Decimal("1"),
            shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("1")}], user=self.admin,
        )
        with self.assertRaises(ValidationError):
            issue_packing_piece(
                recipe_id=recipe.id, wip_product_id=self.piece.id, quantity=Decimal("1"),
                shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("1")}], user=self.admin,
            )

    def test_issue_piece_insufficient_stock_raises(self):
        recipe = create_packing_recipe(name="Packing", user=self.admin)
        with self.assertRaises(ValidationError):
            issue_packing_piece(
                recipe_id=recipe.id, wip_product_id=self.piece.id, quantity=Decimal("999"),
                shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("999")}], user=self.admin,
            )

    def test_finish_requires_description(self):
        recipe = create_packing_recipe(name="Packing", user=self.admin)
        issue_packing_piece(
            recipe_id=recipe.id, wip_product_id=self.piece.id, quantity=Decimal("1"),
            shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("1")}], user=self.admin,
        )
        issue_packing_material(
            recipe_id=recipe.id, product_id=self.packing_material.id, quantity=Decimal("0.1"),
            shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("0.1")}], user=self.admin,
        )
        with self.assertRaises(ValidationError):
            finish_packing_recipe(
                recipe_id=recipe.id,
                shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("1")}],
                user=self.admin,
            )

    def test_finish_requires_both_piece_and_material_issued(self):
        recipe = create_packing_recipe(name="Packing", user=self.admin)
        update_recipe_description(recipe_id=recipe.id, description="x", user=self.admin)
        with self.assertRaises(ValidationError):
            finish_packing_recipe(recipe_id=recipe.id, shelf_allocations=[], user=self.admin)

    def test_update_issued_piece_increase_and_decrease(self):
        recipe = create_packing_recipe(name="Packing", user=self.admin)
        issue_packing_piece(
            recipe_id=recipe.id, wip_product_id=self.piece.id, quantity=Decimal("2"),
            shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("2")}], user=self.admin,
        )
        updated = update_packing_issued_piece(
            recipe_id=recipe.id, new_quantity=Decimal("5"),
            shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("3")}], user=self.admin,
        )
        self.assertEqual(updated.quantity, Decimal("5"))
        updated = update_packing_issued_piece(
            recipe_id=recipe.id, new_quantity=Decimal("2"),
            shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("3")}], user=self.admin,
        )
        self.assertEqual(updated.quantity, Decimal("2"))
        self.piece.refresh_from_db()
        self.assertEqual(self.piece.inventory.quantity, Decimal("8"))  # 10 - 2 net issued

    def test_update_issued_material_increase_and_decrease(self):
        recipe = create_packing_recipe(name="Packing", user=self.admin)
        issue_packing_material(
            recipe_id=recipe.id, product_id=self.packing_material.id, quantity=Decimal("1"),
            shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("1")}], user=self.admin,
        )
        updated = update_packing_issued_material(
            recipe_id=recipe.id, new_quantity=Decimal("3"),
            shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("2")}], user=self.admin,
        )
        self.assertEqual(updated.quantity, Decimal("3"))
        updated = update_packing_issued_material(
            recipe_id=recipe.id, new_quantity=Decimal("1"),
            shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("2")}], user=self.admin,
        )
        self.assertEqual(updated.quantity, Decimal("1"))
        self.packing_material.refresh_from_db()
        self.assertEqual(self.packing_material.inventory.quantity, Decimal("9"))  # 10 - 1 net issued


class PackingApiViewTests(PackingRecipeTestBase):
    def test_non_admin_gets_403_on_list(self):
        normal = make_normal_user()
        request = self.factory.get("/production/packing-recipes/")
        force_authenticate(request, user=normal)
        response = PackingRecipeListCreateView.as_view()(request)
        self.assertEqual(response.status_code, 403)

    def test_admin_can_list_and_retrieve(self):
        recipe = create_packing_recipe(name="Packing", user=self.admin)
        request = self.factory.get("/production/packing-recipes/")
        force_authenticate(request, user=self.admin)
        response = PackingRecipeListCreateView.as_view()(request)
        self.assertEqual(response.status_code, 200)

        request2 = self.factory.get(f"/production/packing-recipes/{recipe.id}/")
        force_authenticate(request2, user=self.admin)
        response2 = PackingRecipeRetrieveView.as_view()(request2, pk=recipe.id)
        self.assertEqual(response2.status_code, 200)

    def test_retrieve_query_count_is_bounded(self):
        """A detail view's query count must be a small fixed number, not proportional to child-row count — architecture.md's N+1 rule."""
        recipe = create_packing_recipe(name="Packing", user=self.admin)
        issue_packing_piece(
            recipe_id=recipe.id, wip_product_id=self.piece.id, quantity=Decimal("4"),
            shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("4")}], user=self.admin,
        )
        issue_packing_material(
            recipe_id=recipe.id, product_id=self.packing_material.id, quantity=Decimal("0.4"),
            shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("0.4")}], user=self.admin,
        )
        update_recipe_description(recipe_id=recipe.id, description="x", user=self.admin)
        finish_packing_recipe(
            recipe_id=recipe.id,
            shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("4")}],
            user=self.admin,
        )

        request = self.factory.get(f"/production/packing-recipes/{recipe.id}/")
        force_authenticate(request, user=self.admin)
        with CaptureQueriesContext(connection) as ctx:
            response = PackingRecipeRetrieveView.as_view()(request, pk=recipe.id)
        self.assertEqual(response.status_code, 200)
        self.assertLess(len(ctx.captured_queries), 25)


class WipProductCodeTests(PackingRecipeTestBase):
    def test_new_wip_products_get_a_code(self):
        self.assertIsNotNone(self.whole_core.code)
        self.assertTrue(self.whole_core.code.startswith("WIP-"))
        self.assertIsNotNone(self.piece.code)
        self.assertTrue(self.piece.code.startswith("WIP-"))
        self.assertNotEqual(self.whole_core.code, self.piece.code)

    def test_backfill_command_is_idempotent(self):
        from django.core.management import call_command
        codes_before = list(WipProduct.objects.order_by("id").values_list("id", "code"))
        call_command("backfill_wip_product_codes")
        codes_after = list(WipProduct.objects.order_by("id").values_list("id", "code"))
        self.assertEqual(codes_before, codes_after)


class FgProductCodeTests(PackingRecipeTestBase):
    def test_fg_product_gets_a_code(self):
        recipe = create_packing_recipe(name="Packing", user=self.admin)
        issue_packing_piece(
            recipe_id=recipe.id, wip_product_id=self.piece.id, quantity=Decimal("1"),
            shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("1")}], user=self.admin,
        )
        issue_packing_material(
            recipe_id=recipe.id, product_id=self.packing_material.id, quantity=Decimal("0.1"),
            shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("0.1")}], user=self.admin,
        )
        update_recipe_description(recipe_id=recipe.id, description="x", user=self.admin)
        finished = finish_packing_recipe(
            recipe_id=recipe.id,
            shelf_allocations=[{"shelf_id": self.shelf.id, "quantity": Decimal("1")}],
            user=self.admin,
        )
        fg_product = finished.packing_output_item.fg_product
        self.assertIsNotNone(fg_product.code)
        self.assertTrue(fg_product.code.startswith("FG-"))
