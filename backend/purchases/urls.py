from django.urls import path

from .views import (
    # Lookup tables
    FamilyListView,
    FamilyRetrieveView,
    ShelfListCreateView,
    ShelfRetrieveUpdateDestroyView,
    CandidateShelvesForProductView,
    AutoAllocateShelvesView,
    MoveStockView,

    # Fixed-product attribute lookups (Jumbo/Cores/Packing/Cartons)
    JumboNameListCreateView,
    JumboNameRetrieveUpdateDestroyView,
    CoreNameListCreateView,
    CoreNameRetrieveUpdateDestroyView,
    CoreLengthListCreateView,
    CoreLengthRetrieveUpdateDestroyView,
    CoreThicknessListCreateView,
    CoreThicknessRetrieveUpdateDestroyView,
    PackingSizeListCreateView,
    PackingSizeRetrieveUpdateDestroyView,
    CartonSizeListCreateView,
    CartonSizeRetrieveUpdateDestroyView,

    # Supplier
    SupplierListCreateView,
    SupplierRetrieveUpdateDestroyView,
    SupplierOutstandingListView,
    SupplierPayableSummaryView,
    SupplierOutstandingOrdersView,
    AllSupplierPaymentsView,

    # Product
    ProductListView,
    ProductRetrieveView,

    # Purchase item / return item shelf allocations
    SetPurchaseItemShelfAllocationsView,
    SetPurchaseReturnItemShelfAllocationsView,

    # Purchase Orders
    PurchaseOrderListCreateView,
    PurchaseOrderRetrieveUpdateDestroyView,
    PurchaseOrderConfirmView,
    DraftPurchaseOrderListView,
    ConfirmedPurchaseOrderListView,
    AllOutstandingOrdersView,

    # Family-specific purchase intake
    JumboPurchaseCreateView,
    CorePurchaseCreateView,
    PackingPurchaseCreateView,
    CartonPurchaseCreateView,
    JumboExactLengthCorrectionView,
    PurchaseBatchListView,

    # Supplier Payments
    SupplierPaymentListCreateView,
    SupplierPaymentDestroyView,
    PurchaseOrderPaymentSummaryView,

    # Purchase Returns
    PurchaseReturnListCreateView,
    AllPurchaseReturnsListView,
    PurchaseReturnAcceptView,
    PurchaseReturnRetrieveUpdateDestroyView,

    # PDF
    PurchaseOrderPrintView,
    PurchaseOrderSavePDFView,
    PurchaseOrderSavedPDFListView,
    SavedPurchaseOrderPDFDeleteView,

    # Lost Inventory
    LostInventoryFifoPreviewView,
    LostInventoryListCreateView,
    LostInventoryRetrieveView,
    MarkLostInventoryFoundView,
)

urlpatterns = [

    # -----------------------------------------------------------------------
    # Lookup tables
    # -----------------------------------------------------------------------
    path("families/",            FamilyListView.as_view(),     name="family-list"),
    path("families/<int:pk>/",   FamilyRetrieveView.as_view(), name="family-detail"),

    # Fixed-product attribute lookups (Jumbo/Cores/Packing/Cartons)
    path("jumbo-names/",             JumboNameListCreateView.as_view(),             name="jumbo-name-list-create"),
    path("jumbo-names/<int:pk>/",    JumboNameRetrieveUpdateDestroyView.as_view(),  name="jumbo-name-detail"),
    path("core-names/",               CoreNameListCreateView.as_view(),             name="core-name-list-create"),
    path("core-names/<int:pk>/",      CoreNameRetrieveUpdateDestroyView.as_view(),  name="core-name-detail"),
    path("core-lengths/",            CoreLengthListCreateView.as_view(),            name="core-length-list-create"),
    path("core-lengths/<int:pk>/",   CoreLengthRetrieveUpdateDestroyView.as_view(), name="core-length-detail"),
    path("core-thicknesses/",        CoreThicknessListCreateView.as_view(),         name="core-thickness-list-create"),
    path("core-thicknesses/<int:pk>/", CoreThicknessRetrieveUpdateDestroyView.as_view(), name="core-thickness-detail"),
    path("packing-sizes/",           PackingSizeListCreateView.as_view(),           name="packing-size-list-create"),
    path("packing-sizes/<int:pk>/",  PackingSizeRetrieveUpdateDestroyView.as_view(), name="packing-size-detail"),
    path("carton-sizes/",            CartonSizeListCreateView.as_view(),            name="carton-size-list-create"),
    path("carton-sizes/<int:pk>/",   CartonSizeRetrieveUpdateDestroyView.as_view(), name="carton-size-detail"),

    path("shelves/",             ShelfListCreateView.as_view(),                name="shelf-list-create"),

    # static paths (candidates/, move/) BEFORE dynamic <int:pk> paths
    path("shelves/candidates/",  CandidateShelvesForProductView.as_view(),     name="shelf-candidates"),
    path("shelves/auto-allocate/", AutoAllocateShelvesView.as_view(),          name="shelf-auto-allocate"),
    path("shelves/move/",        MoveStockView.as_view(),                      name="shelf-move-stock"),

    path("shelves/<int:pk>/",    ShelfRetrieveUpdateDestroyView.as_view(),     name="shelf-detail"),
    # shelves/<pk>/stock/ moved to inventory.urls (mechanical extraction) —
    # mounted at the same "api/" prefix, so the final path is unchanged.

    # -----------------------------------------------------------------------
    # Supplier
    # IMPORTANT: static paths (outstanding/) BEFORE dynamic paths (<int:pk>/)
    # -----------------------------------------------------------------------
    path("suppliers/",
         SupplierListCreateView.as_view(),
         name="supplier-list-create"),

    path("suppliers/outstanding/",
         SupplierOutstandingListView.as_view(),
         name="supplier-outstanding-list"),

    path("suppliers/<int:pk>/",
         SupplierRetrieveUpdateDestroyView.as_view(),
         name="supplier-detail"),

    path("suppliers/<int:pk>/payable-summary/",
         SupplierPayableSummaryView.as_view(),
         name="supplier-payable-summary"),

    path("suppliers/<int:pk>/outstanding-orders/",
         SupplierOutstandingOrdersView.as_view(),
         name="supplier-outstanding-orders"),

    # -----------------------------------------------------------------------
    # Product
    # -----------------------------------------------------------------------
    path("products/",            ProductListView.as_view(),                   name="product-list-create"),
    path("products/<int:pk>/",   ProductRetrieveView.as_view(),               name="product-detail"),

    # -----------------------------------------------------------------------
    # Purchase Orders
    # IMPORTANT: all static paths BEFORE dynamic <int:pk> paths
    # -----------------------------------------------------------------------
    path("orders/",
         PurchaseOrderListCreateView.as_view(),
         name="purchase-order-list-create"),

    path("orders/drafts/",
         DraftPurchaseOrderListView.as_view(),
         name="purchase-order-drafts"),

    path("orders/confirmed/",
         ConfirmedPurchaseOrderListView.as_view(),
         name="purchase-order-confirmed"),

    path("orders/outstanding/",
         AllOutstandingOrdersView.as_view(),
         name="all-outstanding-orders"),

    # Family-specific purchase intake
    path("jumbo-purchases/",   JumboPurchaseCreateView.as_view(),   name="jumbo-purchase-create"),
    path("core-purchases/",    CorePurchaseCreateView.as_view(),    name="core-purchase-create"),
    path("packing-purchases/", PackingPurchaseCreateView.as_view(), name="packing-purchase-create"),
    path("carton-purchases/",  CartonPurchaseCreateView.as_view(),  name="carton-purchase-create"),
    path("purchase-batches/",  PurchaseBatchListView.as_view(),     name="purchase-batch-list"),

    path("orders/<int:pk>/",
         PurchaseOrderRetrieveUpdateDestroyView.as_view(),
         name="purchase-order-detail"),

    path("orders/<int:pk>/confirm/",
         PurchaseOrderConfirmView.as_view(),
         name="purchase-order-confirm"),

    path("orders/<int:pk>/payment-summary/",
         PurchaseOrderPaymentSummaryView.as_view(),
         name="purchase-order-payment-summary"),

    path("orders/<int:pk>/print/",
         PurchaseOrderPrintView.as_view(),
         name="purchase-order-print"),

    path("orders/<int:pk>/pdf/save/",
         PurchaseOrderSavePDFView.as_view(),
         name="purchase-order-pdf-save"),

    path("orders/<int:pk>/pdf/",
         PurchaseOrderSavedPDFListView.as_view(),
         name="purchase-order-pdf-list"),

    # -----------------------------------------------------------------------
    # Purchase item / return item shelf allocations
    # -----------------------------------------------------------------------
    path("purchase-items/<int:pk>/shelf-allocations/",
         SetPurchaseItemShelfAllocationsView.as_view(),
         name="purchase-item-shelf-allocations"),

    path("purchase-items/<int:pk>/correct-jumbo-length/",
         JumboExactLengthCorrectionView.as_view(),
         name="purchase-item-correct-jumbo-length"),

    path("return-items/<int:pk>/shelf-allocations/",
         SetPurchaseReturnItemShelfAllocationsView.as_view(),
         name="purchase-return-item-shelf-allocations"),

    # -----------------------------------------------------------------------
    # Supplier Payments (nested under order)
    # -----------------------------------------------------------------------
    path("orders/<int:order_id>/payments/",
         SupplierPaymentListCreateView.as_view(),
         name="supplier-payment-list-create"),

    path("payments/",
         AllSupplierPaymentsView.as_view(),
         name="supplier-payment-list-all"),

    path("payments/<int:pk>/",
         SupplierPaymentDestroyView.as_view(),
         name="supplier-payment-delete"),

    # -----------------------------------------------------------------------
    # Purchase Returns
    # -----------------------------------------------------------------------
    path("returns/",
         AllPurchaseReturnsListView.as_view(),
         name="purchase-return-list-all"),

    path("returns/<int:pk>/accept/",
         PurchaseReturnAcceptView.as_view(),
         name="purchase-return-accept"),

    path("returns/<int:pk>/",
         PurchaseReturnRetrieveUpdateDestroyView.as_view(),
         name="purchase-return-detail"),

    path("orders/<int:order_id>/returns/",
         PurchaseReturnListCreateView.as_view(),
         name="purchase-return-list-create"),

    # -----------------------------------------------------------------------
    # Saved PDFs
    # -----------------------------------------------------------------------
    path("pdf/<int:saved_pdf_id>/",
         SavedPurchaseOrderPDFDeleteView.as_view(),
         name="purchase-order-pdf-delete"),

    # -----------------------------------------------------------------------
    # Inventory routes (inventory/, inventory/stats/, inventory/low-stock/,
    # inventory/out-of-stock/, inventory/<product_id>/) moved to
    # inventory.urls — mounted at the same "api/" prefix in backend/urls.py,
    # so the final paths are unchanged.
    # -----------------------------------------------------------------------

    # -----------------------------------------------------------------------
    # Lost Inventory
    # IMPORTANT: static paths (fifo-preview/) BEFORE dynamic paths (<int:pk>/)
    # -----------------------------------------------------------------------
    path("lost-inventory/",
         LostInventoryListCreateView.as_view(),
         name="lost-inventory-list-create"),

    path("lost-inventory/fifo-preview/",
         LostInventoryFifoPreviewView.as_view(),
         name="lost-inventory-fifo-preview"),

    path("lost-inventory/<int:pk>/",
         LostInventoryRetrieveView.as_view(),
         name="lost-inventory-detail"),

    path("lost-inventory/items/<int:item_id>/found/",
         MarkLostInventoryFoundView.as_view(),
         name="lost-inventory-item-found"),
]