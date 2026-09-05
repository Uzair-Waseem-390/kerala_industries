from django.urls import path

from .views import (
    CombinedInventoryListView, CombinedInventoryStatsView, InventoryListView,
    InventoryRetrieveView, InventoryStatsView, LowStockInventoryListView,
    OutOfStockInventoryListView, ShelfStockListView,
)

urlpatterns = [

    # -----------------------------------------------------------------------
    # Shelf stock (nested under the purchases Shelf routes' pk)
    # -----------------------------------------------------------------------
    path("shelves/<int:pk>/stock/", ShelfStockListView.as_view(),          name="shelf-stock-list"),

    # -----------------------------------------------------------------------
    # Inventory
    # -----------------------------------------------------------------------
    path("inventory/",
         InventoryListView.as_view(),
         name="inventory-list"),

    path("inventory/all/",
         CombinedInventoryListView.as_view(),
         name="inventory-all"),

    path("inventory/all/stats/",
         CombinedInventoryStatsView.as_view(),
         name="inventory-all-stats"),

    path("inventory/stats/",
         InventoryStatsView.as_view(),
         name="inventory-stats"),

    path("inventory/low-stock/",
         LowStockInventoryListView.as_view(),
         name="inventory-low-stock"),

    path("inventory/out-of-stock/",
         OutOfStockInventoryListView.as_view(),
         name="inventory-out-of-stock"),

    path("inventory/<int:product_id>/",
         InventoryRetrieveView.as_view(),
         name="inventory-detail"),
]
