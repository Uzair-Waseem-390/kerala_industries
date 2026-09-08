from django.urls import path

from .views import (
    EmployeeListCreateView,
    EmployeeRetrieveUpdateDestroyView,
    FactoryOverheadSettingView,
    MachineListCreateView,
    MachineRetrieveUpdateDestroyView,
    PayableEntityDeleteView,
    PayableEntityListView,
    PayableEntityPaymentListView,
    PayableEntityRetrieveView,
    PayableEntityStatsView,
    PaymentListCreateView,
    PaymentRetrieveDestroyView,
)

urlpatterns = [
    # Page 2 — Employees (Direct Labor)
    path("employees/",     EmployeeListCreateView.as_view(),          name="mfg-employee-list-create"),
    path("employees/<int:pk>/", EmployeeRetrieveUpdateDestroyView.as_view(), name="mfg-employee-detail"),

    # Page 3 — Machines + Factory Overhead setting
    path("machines/",      MachineListCreateView.as_view(),           name="mfg-machine-list-create"),
    path("machines/<int:pk>/", MachineRetrieveUpdateDestroyView.as_view(), name="mfg-machine-detail"),
    path("factory-overhead-setting/", FactoryOverheadSettingView.as_view(), name="mfg-foh-setting"),

    # Page 4 — Payable Entities registry
    path("payable-entities/",          PayableEntityListView.as_view(),        name="mfg-payable-entity-list"),
    path("payable-entities/<int:pk>/", PayableEntityRetrieveView.as_view(),    name="mfg-payable-entity-detail"),
    path("payable-entities/<int:pk>/stats/",    PayableEntityStatsView.as_view(),    name="mfg-payable-entity-stats"),
    path("payable-entities/<int:pk>/payments/", PayableEntityPaymentListView.as_view(), name="mfg-payable-entity-payments"),
    path("payable-entities/<int:pk>/delete/",   PayableEntityDeleteView.as_view(),   name="mfg-payable-entity-delete"),

    # Page 4 (record) / Page 5 (all payments)
    path("payments/",      PaymentListCreateView.as_view(),           name="mfg-payment-list-create"),
    path("payments/<int:pk>/", PaymentRetrieveDestroyView.as_view(),  name="mfg-payment-detail"),
]
