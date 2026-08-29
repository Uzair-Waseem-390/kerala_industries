from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsAdminOrSuperuserOrReadOnly
from .selectors import (
    get_all_inventory, get_inventory_by_product_id, get_inventory_stats,
    get_low_stock_inventory, get_out_of_stock_inventory, get_shelf_stock_rows,
)
from .serializers import (
    InventoryReadSerializer, InventoryStatsSerializer, ShelfStockReadSerializer,
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
        shelf       : shelf id

    Stats cards moved to GET /purchases/inventory/stats/ (O(1) singleton
    read) — the old embedded stats re-scanned the filtered queryset three
    extra times on every page load.
    """
    permission_classes = [IsAdminOrSuperuserOrReadOnly]
    serializer_class   = InventoryReadSerializer

    def get_queryset(self):
        p = self.request.query_params
        return get_all_inventory(search=p.get("search"))


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
    Same filters as the main inventory list: search, shelf.
    """
    permission_classes = [IsAdminOrSuperuserOrReadOnly]
    serializer_class   = InventoryReadSerializer

    def get_queryset(self):
        p = self.request.query_params
        return get_low_stock_inventory(search=p.get("search"))


class OutOfStockInventoryListView(generics.ListAPIView):
    """
    GET /purchases/inventory/out-of-stock/
    Breakdown behind the "Out of Stock" card (quantity <= 0).
    Same filters as the main inventory list: search, shelf.
    """
    permission_classes = [IsAdminOrSuperuserOrReadOnly]
    serializer_class   = InventoryReadSerializer

    def get_queryset(self):
        p = self.request.query_params
        return get_out_of_stock_inventory(search=p.get("search"))


class InventoryRetrieveView(generics.RetrieveAPIView):
    permission_classes = [IsAdminOrSuperuserOrReadOnly]
    serializer_class   = InventoryReadSerializer

    def get_object(self):
        return get_inventory_by_product_id(self.kwargs["product_id"])
