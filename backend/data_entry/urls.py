from django.urls import path

from .views import (
    CustomerOpeningBalanceListCreateView,
    OpeningCashListCreateView,
    OpeningFgStockListCreateView,
    OpeningInvestorInvestmentListCreateView,
    OpeningStockListCreateView,
    OpeningWipStockListCreateView,
    SupplierOpeningBalanceListCreateView,
)

urlpatterns = [
    path("supplier-opening-balance/",    SupplierOpeningBalanceListCreateView.as_view(),    name="supplier-opening-balance"),
    path("customer-opening-balance/",    CustomerOpeningBalanceListCreateView.as_view(),    name="customer-opening-balance"),
    path("opening-cash/",                OpeningCashListCreateView.as_view(),               name="opening-cash"),
    path("opening-stock/",               OpeningStockListCreateView.as_view(),              name="opening-stock"),
    path("opening-wip-stock/",           OpeningWipStockListCreateView.as_view(),           name="opening-wip-stock"),
    path("opening-fg-stock/",            OpeningFgStockListCreateView.as_view(),            name="opening-fg-stock"),
    path("opening-investor-investment/", OpeningInvestorInvestmentListCreateView.as_view(), name="opening-investor-investment"),
]
