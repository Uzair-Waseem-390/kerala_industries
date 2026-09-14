from datetime import datetime, time
from decimal import ROUND_HALF_UP, Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from billing.models import Invoice, InvoiceItem, Return, ReturnItem
from inventory.models import FgInventory, Inventory, WipInventory
from production.models import (
    CuttingBreakdownItem, CuttingMaterialConsumption, PackingIssuedPiece,
    PackingOutputItem, Recipe, RecipeBreakdownItem,
)
from purchases.models import (
    LostInventoryItem, LostInventoryRecovery, PurchaseItem, PurchaseOrder,
    PurchaseReturn, PurchaseReturnItem,
)
from purchases.utils import meters_to_yards


def _as_datetime(value):
    """Normalizes a date or datetime to an aware datetime at local midnight
    (dates) so every event source sorts on one comparable timeline. Events
    that only have a DateField (LostInventoryRecovery.recovered_at) lose
    intra-day ordering against same-day datetime events — an accepted,
    unavoidable precision limit of reconstructing history from what was
    actually recorded, not a correctness bug in the replay itself."""
    if isinstance(value, datetime):
        return value
    return timezone.make_aware(datetime.combine(value, time.min))


def _replay(events: list) -> tuple:
    """
    Shared replay core for RM/WIP/FG: sorts events by (timestamp,
    cost-events-last-on-ties — a same-day cost event applies after
    same-day neutral events, so a same-day sale/consumption is reflected
    in the weight used by that event's average update), then walks them
    applying the SAME unified moving-average formula
    inventory.services._apply_avg_unit_cost uses at write time — a cost
    event (positive OR negative quantity_delta, e.g. a purchase vs. a
    purchase return) moves the average; a neutral event only moves qty.
    Returns (final_qty, final_avg).
    """
    events = sorted(events, key=lambda e: (e[0], e[1]))
    qty = Decimal("0")
    avg = Decimal("0")
    for _ts, _tiebreak, is_cost_event, delta, cost in events:
        if is_cost_event:
            new_qty = qty + delta
            avg = ((avg * qty) + (cost * delta)) / new_qty if new_qty > 0 else Decimal("0")
            avg = avg.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            qty = max(Decimal("0"), new_qty)
        else:
            qty = max(Decimal("0"), qty + delta)
    return qty, avg


class Command(BaseCommand):
    """
    One-time historical reconstruction of avg_unit_cost across all three
    inventory stages (RM/WIP/FG) — replays EVERY event that ever changed a
    product's stock, in the order it really happened, recalculating the
    moving average ONLY at cost events (a real confirmed purchase or an
    accepted purchase return for RM; a finished Rewinding/Cutting/Packing
    recipe for WIP/FG — using the real quantity-on-hand at that moment as
    the weight), exactly matching the invariant inventory.services
    .sync_inventory/sync_wip_inventory/sync_fg_inventory now enforce going
    forward. Neutral events (sales, customer returns, lost, recovered, WIP
    consumed into a downstream recipe) only move the replayed quantity,
    never the average.

    Deliberately NOT "seed from today's live batch-walk snapshot" — for any
    product that already had a purchase return/sale/etc. before this fix,
    today's remaining-batch composition no longer reflects a purchase-only
    average. Replaying full history is the only way to recover the number
    the average would show if it had never been able to move except on a
    purchase or purchase return.

    Idempotent by default: only reconstructs products where avg_unit_cost
    is still 0 (never seeded) — safe to re-run after a partial/interrupted
    run. --force reprocesses every product regardless.

    Sanity check: after replay, the reconstructed quantity is compared
    against the real Inventory/WipInventory/FgInventory.quantity for that
    product — a mismatch means some quantity-moving event isn't covered by
    this replay (or a data integrity issue predates it) and is reported,
    never silently ignored; avg_unit_cost is still written (it's the best
    reconstruction available), but the mismatch is surfaced for manual
    review.
    """

    help = "Reconstructs avg_unit_cost (RM/WIP/FG) by replaying full stock history in event order."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force", action="store_true",
            help="Reprocess every product, even ones with a non-zero avg_unit_cost already.",
        )

    def handle(self, *args, **options):
        force = options["force"]
        seeded = 0
        mismatches = []

        seeded_rm, mismatches_rm = self._backfill_rm(force)
        seeded_wip, mismatches_wip = self._backfill_wip(force)
        seeded_fg, mismatches_fg = self._backfill_fg(force)
        seeded = seeded_rm + seeded_wip + seeded_fg
        mismatches = mismatches_rm + mismatches_wip + mismatches_fg

        self.stdout.write(self.style.SUCCESS(f"Reconstructed avg_unit_cost for {seeded} product(s) (RM {seeded_rm}, WIP {seeded_wip}, FG {seeded_fg})."))
        if mismatches:
            self.stdout.write(self.style.WARNING(
                f"{len(mismatches)} product(s) had a replayed quantity that didn't match "
                f"the real Inventory.quantity — avg_unit_cost was still written (best "
                f"available reconstruction), but review these for a missing event source "
                f"or pre-existing data issue: "
                + ", ".join(f"{kind} product {pid} (replayed {rq} vs actual {aq})" for kind, pid, rq, aq in mismatches)
            ))

    # -----------------------------------------------------------------
    # RM
    # -----------------------------------------------------------------
    def _backfill_rm(self, force):
        inventories = Inventory.objects.filter(quantity__gt=0)
        if not force:
            inventories = inventories.filter(avg_unit_cost=0)
        inventories = list(inventories)
        product_ids = [inv.product_id for inv in inventories]
        events_by_product = {pid: [] for pid in product_ids}

        purchases = PurchaseItem.objects.filter(
            product_id__in=product_ids, is_deleted=False,
            order__status=PurchaseOrder.Status.CONFIRMED, order__confirmed_at__isnull=False,
        ).select_related("order")
        for item in purchases:
            unit_cost = item.total_price / item.quantity if item.quantity else item.unit_price
            events_by_product[item.product_id].append((_as_datetime(item.order.confirmed_at), 1, True, item.quantity, unit_cost))

        purchase_returns = PurchaseReturnItem.objects.filter(
            purchase_item__product_id__in=product_ids,
            return_record__status=PurchaseReturn.Status.ACCEPTED, return_record__accepted_at__isnull=False,
        ).select_related("return_record", "purchase_item")
        for ritem in purchase_returns:
            batch = ritem.purchase_item
            unit_cost = batch.total_price / batch.quantity if batch.quantity else batch.unit_price
            events_by_product[batch.product_id].append((_as_datetime(ritem.return_record.accepted_at), 1, True, -ritem.quantity, unit_cost))

        sales = InvoiceItem.objects.filter(
            rm_product_id__in=product_ids, invoice__is_deleted=False, invoice__confirmed_at__isnull=False,
        ).exclude(invoice__status=Invoice.Status.DRAFT).select_related("invoice")
        for item in sales:
            events_by_product[item.rm_product_id].append((_as_datetime(item.invoice.confirmed_at), 0, False, -item.quantity, None))

        sales_returns = ReturnItem.objects.filter(
            invoice_item__rm_product_id__in=product_ids,
            return_record__status=Return.Status.ACCEPTED, return_record__accepted_at__isnull=False,
        ).select_related("return_record", "invoice_item")
        for ritem in sales_returns:
            events_by_product[ritem.invoice_item.rm_product_id].append((_as_datetime(ritem.return_record.accepted_at), 0, False, ritem.quantity, None))

        lost_items = LostInventoryItem.objects.filter(
            rm_product_id__in=product_ids, record__is_deleted=False,
        ).select_related("record")
        for litem in lost_items:
            events_by_product[litem.rm_product_id].append((_as_datetime(litem.record.created_at), 0, False, -litem.quantity, None))

        recoveries = LostInventoryRecovery.objects.filter(lost_item__rm_product_id__in=product_ids).select_related("lost_item")
        for rec in recoveries:
            events_by_product[rec.lost_item.rm_product_id].append((_as_datetime(rec.recovered_at), 0, False, rec.quantity, None))

        # Jumbo exact-length correction — neutral (re-measures the same
        # batch's own yards, no new cost information). No per-correction
        # history is stored (a second correction is relative to the
        # current quantity, per purchases.services.correct_jumbo_exact_length's
        # own docstring), so this replays as a single net delta since the
        # original purchase (current quantity vs. the fixed
        # expected_length_m converted to yards), timestamped at the item's
        # updated_at as the closest real record of when it happened — same
        # kind of proxy-timestamp precision limit as PackingIssuedPiece
        # above.
        corrections = PurchaseItem.objects.filter(
            product_id__in=product_ids, is_deleted=False, exact_length_m__isnull=False,
            expected_length_m__isnull=False,
        )
        for item in corrections:
            original_quantity = meters_to_yards(item.expected_length_m)
            delta = item.quantity - original_quantity
            if delta != 0:
                events_by_product[item.product_id].append((_as_datetime(item.updated_at), 0, False, delta, None))

        return self._apply(inventories, events_by_product, "RM")

    # -----------------------------------------------------------------
    # WIP (Rewinding cores + Cutting pieces share WipInventory)
    # -----------------------------------------------------------------
    def _backfill_wip(self, force):
        inventories = WipInventory.objects.filter(quantity__gt=0)
        if not force:
            inventories = inventories.filter(avg_unit_cost=0)
        inventories = list(inventories)
        product_ids = [inv.product_id for inv in inventories]
        events_by_product = {pid: [] for pid in product_ids}

        core_batches = RecipeBreakdownItem.objects.filter(
            wip_product_id__in=product_ids, is_deleted=False, recipe__status=Recipe.Status.FINISHED,
            recipe__finished_at__isnull=False,
        ).select_related("recipe")
        for item in core_batches:
            events_by_product[item.wip_product_id].append((_as_datetime(item.recipe.finished_at), 1, True, item.quantity, item.full_unit_cost_snapshot or Decimal("0")))

        piece_batches = CuttingBreakdownItem.objects.filter(
            wip_product_id__in=product_ids, is_deleted=False, recipe__status=Recipe.Status.FINISHED,
            recipe__finished_at__isnull=False,
        ).select_related("recipe")
        for item in piece_batches:
            events_by_product[item.wip_product_id].append((_as_datetime(item.recipe.finished_at), 1, True, item.quantity, item.full_unit_cost_snapshot or Decimal("0")))

        # Cores consumed into Cutting — neutral (FIFO consumption ledger).
        consumptions = CuttingMaterialConsumption.objects.filter(
            wip_batch__wip_product_id__in=product_ids,
        ).select_related("wip_batch")
        for c in consumptions:
            events_by_product[c.wip_batch.wip_product_id].append((_as_datetime(c.created_at), 0, False, -c.quantity, None))

        # Pieces issued into Packing — neutral. No per-consumption timestamp
        # exists on this row; the recipe's own created_at is the closest
        # real record of when the issuance happened.
        issuances = PackingIssuedPiece.objects.filter(wip_product_id__in=product_ids).select_related("recipe")
        for pip in issuances:
            events_by_product[pip.wip_product_id].append((_as_datetime(pip.recipe.created_at), 0, False, -pip.quantity, None))

        lost_items = LostInventoryItem.objects.filter(
            wip_product_id__in=product_ids, record__is_deleted=False,
        ).select_related("record")
        for litem in lost_items:
            events_by_product[litem.wip_product_id].append((_as_datetime(litem.record.created_at), 0, False, -litem.quantity, None))

        recoveries = LostInventoryRecovery.objects.filter(lost_item__wip_product_id__in=product_ids).select_related("lost_item")
        for rec in recoveries:
            events_by_product[rec.lost_item.wip_product_id].append((_as_datetime(rec.recovered_at), 0, False, rec.quantity, None))

        return self._apply(inventories, events_by_product, "WIP")

    # -----------------------------------------------------------------
    # FG
    # -----------------------------------------------------------------
    def _backfill_fg(self, force):
        inventories = FgInventory.objects.filter(quantity__gt=0)
        if not force:
            inventories = inventories.filter(avg_unit_cost=0)
        inventories = list(inventories)
        product_ids = [inv.product_id for inv in inventories]
        events_by_product = {pid: [] for pid in product_ids}

        output_batches = PackingOutputItem.objects.filter(
            fg_product_id__in=product_ids, is_deleted=False, recipe__status=Recipe.Status.FINISHED,
            recipe__finished_at__isnull=False,
        ).select_related("recipe")
        for item in output_batches:
            events_by_product[item.fg_product_id].append((_as_datetime(item.recipe.finished_at), 1, True, item.quantity, item.full_unit_cost_snapshot or Decimal("0")))

        sales = InvoiceItem.objects.filter(
            fg_product_id__in=product_ids, invoice__is_deleted=False, invoice__confirmed_at__isnull=False,
        ).exclude(invoice__status=Invoice.Status.DRAFT).select_related("invoice")
        for item in sales:
            events_by_product[item.fg_product_id].append((_as_datetime(item.invoice.confirmed_at), 0, False, -item.quantity, None))

        sales_returns = ReturnItem.objects.filter(
            invoice_item__fg_product_id__in=product_ids,
            return_record__status=Return.Status.ACCEPTED, return_record__accepted_at__isnull=False,
        ).select_related("return_record", "invoice_item")
        for ritem in sales_returns:
            events_by_product[ritem.invoice_item.fg_product_id].append((_as_datetime(ritem.return_record.accepted_at), 0, False, ritem.quantity, None))

        lost_items = LostInventoryItem.objects.filter(
            fg_product_id__in=product_ids, record__is_deleted=False,
        ).select_related("record")
        for litem in lost_items:
            events_by_product[litem.fg_product_id].append((_as_datetime(litem.record.created_at), 0, False, -litem.quantity, None))

        recoveries = LostInventoryRecovery.objects.filter(lost_item__fg_product_id__in=product_ids).select_related("lost_item")
        for rec in recoveries:
            events_by_product[rec.lost_item.fg_product_id].append((_as_datetime(rec.recovered_at), 0, False, rec.quantity, None))

        return self._apply(inventories, events_by_product, "FG")

    # -----------------------------------------------------------------
    def _apply(self, inventories, events_by_product, kind: str):
        seeded = 0
        mismatches = []
        for inv in inventories:
            events = events_by_product.get(inv.product_id, [])
            qty, avg = _replay(events)
            inv.avg_unit_cost = avg
            inv.save(update_fields=["avg_unit_cost"])
            seeded += 1
            if qty != Decimal(inv.quantity):
                mismatches.append((kind, inv.product_id, qty, inv.quantity))
        return seeded, mismatches
