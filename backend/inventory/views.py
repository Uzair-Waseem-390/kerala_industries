from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.paginations import StandardResultsSetPagination

from .permissions import IsAdminOrSuperuserOrReadOnly
from .selectors import (
    get_all_inventory, get_combined_inventory_rows, get_combined_inventory_stats,
    get_inventory_by_product_id, get_inventory_stats, get_low_stock_inventory,
    get_out_of_stock_inventory, get_shelf_stock_rows,
)
from .serializers import (
    CombinedInventoryRowSerializer, InventoryReadSerializer, InventoryStatsSerializer,
    ShelfStockReadSerializer,
)


class ShelfStockListView(generics.ListAPIView):
    """GET /purchases/shelves/<pk>/stock/ — products + quantities on one shelf."""
    permission_classes = [IsAdminOrSuperuserOrReadOnly]
    serializer_class   = ShelfStockReadSerializer

    def get_queryset(self):
        from purchases.selectors import get_shelf_by_id
        get_shelf_by_id(self.kwargs["pk"])  # 404s if the shelf doesn't exist
        return get_shelf_stock_rows(self.kwargs["pk"], search=self.request.query_params.get("search"))


# ---------------------------------------------------------------------------
# Inventory (read for all auth users)
# ---------------------------------------------------------------------------

class InventoryListView(generics.ListAPIView):
    """
    GET /purchases/inventory/
    Available to all authenticated users (including normal users).

    Filter params:
        search      : product name or code (partial match)
        family      : product family id
        shelf       : shelf id

    Stats cards moved to GET /purchases/inventory/stats/ (O(1) singleton
    read) — the old embedded stats re-scanned the filtered queryset three
    extra times on every page load.
    """
    permission_classes = [IsAdminOrSuperuserOrReadOnly]
    serializer_class   = InventoryReadSerializer

    def get_queryset(self):
        p = self.request.query_params
        return get_all_inventory(search=p.get("search"), family_id=p.get("family"))


class InventoryStatsView(APIView):
    """
    GET /purchases/inventory/stats/
    O(1) whole-inventory stats for the Inventory page cards — reads the
    InventoryStatsFlow singleton (kept in sync at write time). Global
    numbers by design: cards always show the full picture; the breakdown
    endpoints handle filtered drill-downs.
    """
    permission_classes = [IsAdminOrSuperuserOrReadOnly]

    def get(self, request):
        return Response(InventoryStatsSerializer(get_inventory_stats()).data)


class LowStockInventoryListView(generics.ListAPIView):
    """
    GET /purchases/inventory/low-stock/
    Breakdown behind the "Low Stock" card (0 < quantity <= threshold).
    Same filters as the main inventory list: search, family, shelf.
    """
    permission_classes = [IsAdminOrSuperuserOrReadOnly]
    serializer_class   = InventoryReadSerializer

    def get_queryset(self):
        p = self.request.query_params
        return get_low_stock_inventory(search=p.get("search"), family_id=p.get("family"))


class OutOfStockInventoryListView(generics.ListAPIView):
    """
    GET /purchases/inventory/out-of-stock/
    Breakdown behind the "Out of Stock" card (quantity <= 0).
    Same filters as the main inventory list: search, family, shelf.
    """
    permission_classes = [IsAdminOrSuperuserOrReadOnly]
    serializer_class   = InventoryReadSerializer

    def get_queryset(self):
        p = self.request.query_params
        return get_out_of_stock_inventory(search=p.get("search"), family_id=p.get("family"))


class InventoryRetrieveView(generics.RetrieveAPIView):
    permission_classes = [IsAdminOrSuperuserOrReadOnly]
    serializer_class   = InventoryReadSerializer

    def get_object(self):
        return get_inventory_by_product_id(self.kwargs["product_id"])


class CombinedInventoryListView(APIView):
    """
    GET /inventory/all/?search=&type=raw_material|wip_core|wip_piece&stock_view=low|out
    Every product's inventory in one merged, paginated list — Raw
    Material and WIP together (Finished Goods has no real inventory model
    yet, see docs/manufacturing-costing-notes.md). Source is a plain
    Python list (see selectors.get_combined_inventory_rows), so pagination
    is applied manually here with the same paginator class every other
    list endpoint uses, rather than DRF's generic ListAPIView (which
    expects a queryset). stock_view narrows to the Low Stock / Out of
    Stock breakdown, same as the RM-only page's cards — still an indexed,
    paginated query, not a live count (the counts themselves are the O(1)
    stats endpoint, unaffected by this param).
    """
    permission_classes = [IsAdminOrSuperuserOrReadOnly]
    pagination_class   = StandardResultsSetPagination

    def get(self, request):
        rows = get_combined_inventory_rows(
            search=request.query_params.get("search"),
            type_filter=request.query_params.get("type"),
            stock_view=request.query_params.get("stock_view"),
        )
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(rows, request, view=self)
        serializer = CombinedInventoryRowSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class CombinedInventoryStatsView(APIView):
    """
    GET /inventory/all/stats/
    O(1) stats for the All Inventory page header (total products, total
    stock, low stock, out of stock) — RM + WIP combined. Two singleton
    reads added together, same as every other stats endpoint in this app;
    never scales with the number of products.
    """
    permission_classes = [IsAdminOrSuperuserOrReadOnly]

    def get(self, request):
        return Response(InventoryStatsSerializer(get_combined_inventory_stats()).data)
