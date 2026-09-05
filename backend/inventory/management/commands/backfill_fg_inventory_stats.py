from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Count, Q, Sum

from inventory.models import LOW_STOCK_THRESHOLD, FgInventory, FgInventoryStatsFlow


class Command(BaseCommand):
    """
    Rebuilds the FgInventoryStatsFlow singleton from live FgInventory data —
    FG-side twin of backfill_inventory_stats/backfill_wip_inventory_stats.
    Idempotent (absolute counts, not deltas). Counts cover inventory rows of
    non-deleted FG products only, matching the live maintenance in
    services.sync_fg_inventory().
    """

    help = "Recompute FgInventoryStatsFlow (total/stock/low-stock/out-of-stock) from live FG inventory."

    def handle(self, *args, **options):
        counts = FgInventory.objects.filter(product__is_deleted=False).aggregate(
            total=Count("id"),
            stock=Sum("quantity"),
            low=Count("id", filter=Q(quantity__gt=0, quantity__lte=LOW_STOCK_THRESHOLD)),
            out=Count("id", filter=Q(quantity__lte=0)),
        )

        flow = FgInventoryStatsFlow.get_instance()
        flow.total_products     = counts["total"]
        flow.total_stock        = counts["stock"] or Decimal("0")
        flow.low_stock_count    = counts["low"]
        flow.out_of_stock_count = counts["out"]
        flow.save(update_fields=[
            "total_products", "total_stock", "low_stock_count", "out_of_stock_count", "last_updated_at",
        ])

        self.stdout.write(self.style.SUCCESS(
            f"FgInventoryStatsFlow rebuilt — total: {counts['total']}, stock: {flow.total_stock}, "
            f"low stock: {counts['low']}, out of stock: {counts['out']}."
        ))
