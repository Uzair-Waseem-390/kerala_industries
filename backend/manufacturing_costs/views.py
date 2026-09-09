from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from payment_methods.mixins import AllocationsListMixin, as_splits

from .permissions import IsAdminOrSuperuser
from .selectors import (
    get_all_employees, get_all_machines, get_all_payable_entities, get_all_payments,
    get_employee_by_id, get_factory_overhead_setting, get_machine_by_id,
    get_manufacturing_costs_stats, get_payable_entity_by_id, get_payable_entity_stats,
    get_payment_by_id, get_payments_for_entity,
)
from .serializers import (
    EmployeeReadSerializer, EmployeeWriteSerializer, FactoryOverheadSettingSerializer,
    MachineReadSerializer, MachineWriteSerializer, ManufacturingCostsStatsSerializer,
    PayableEntityReadSerializer, PayableEntityStatsSerializer, PaymentReadSerializer,
    PaymentWriteSerializer,
)
from .services import (
    create_employee, create_machine, create_payment, delete_employee, delete_machine,
    delete_payable_entity, delete_payment, update_employee, update_factory_overhead_setting,
    update_machine,
)


# ---------------------------------------------------------------------------
# Page 2 — Employees (Direct Labor)
# ---------------------------------------------------------------------------

class EmployeeListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminOrSuperuser]

    def get_serializer_class(self):
        return EmployeeWriteSerializer if self.request.method == "POST" else EmployeeReadSerializer

    def get_queryset(self):
        return get_all_employees(search=self.request.query_params.get("search"))

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        obj = create_employee(
            name=d["name"], monthly_salary=d["monthly_salary"],
            avg_hours_per_day=d["avg_hours_per_day"], working_days_per_month=d["working_days_per_month"],
            user=request.user,
        )
        return Response(EmployeeReadSerializer(obj).data, status=status.HTTP_201_CREATED)


class EmployeeRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminOrSuperuser]

    def get_serializer_class(self):
        return EmployeeWriteSerializer if self.request.method in ("PUT", "PATCH") else EmployeeReadSerializer

    def get_object(self):
        return get_employee_by_id(self.kwargs["pk"])

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        obj = update_employee(pk=self.kwargs["pk"], user=request.user, **serializer.validated_data)
        return Response(EmployeeReadSerializer(obj).data)

    def destroy(self, request, *args, **kwargs):
        delete_employee(pk=self.kwargs["pk"], user=request.user)
        return Response({"detail": "Employee deleted."}, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Page 3 — Machines + Factory Overhead setting
# ---------------------------------------------------------------------------

class MachineListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminOrSuperuser]

    def get_serializer_class(self):
        return MachineWriteSerializer if self.request.method == "POST" else MachineReadSerializer

    def get_queryset(self):
        p = self.request.query_params
        return get_all_machines(search=p.get("search"), category=p.get("category"))

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        obj = create_machine(
            name=d["name"], category=d["category"], avg_hours_per_day=d["avg_hours_per_day"],
            working_days_per_month=d["working_days_per_month"], monthly_repair_cost=d["monthly_repair_cost"],
            user=request.user,
        )
        return Response(MachineReadSerializer(obj).data, status=status.HTTP_201_CREATED)


class MachineRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminOrSuperuser]

    def get_serializer_class(self):
        return MachineWriteSerializer if self.request.method in ("PUT", "PATCH") else MachineReadSerializer

    def get_object(self):
        return get_machine_by_id(self.kwargs["pk"])

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        obj = update_machine(pk=self.kwargs["pk"], user=request.user, **serializer.validated_data)
        return Response(MachineReadSerializer(obj).data)

    def destroy(self, request, *args, **kwargs):
        delete_machine(pk=self.kwargs["pk"], user=request.user)
        return Response({"detail": "Machine deleted."}, status=status.HTTP_200_OK)


class FactoryOverheadSettingView(APIView):
    """GET/PATCH the single Rent+Electricity setting. PATCH cascades a recompute of every Machine.rate_per_hour."""
    permission_classes = [IsAdminOrSuperuser]

    def get(self, request):
        return Response(FactoryOverheadSettingSerializer(get_factory_overhead_setting()).data)

    def patch(self, request):
        serializer = FactoryOverheadSettingSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        obj = update_factory_overhead_setting(
            rent_amount=d.get("rent_amount"), electricity_amount=d.get("electricity_amount"), user=request.user,
        )
        return Response(FactoryOverheadSettingSerializer(obj).data)


# ---------------------------------------------------------------------------
# Page 4 — Payable Entities registry + per-entity payment history/stats
# ---------------------------------------------------------------------------

class PayableEntityListView(generics.ListAPIView):
    permission_classes = [IsAdminOrSuperuser]
    serializer_class   = PayableEntityReadSerializer

    def get_queryset(self):
        p = self.request.query_params
        return get_all_payable_entities(search=p.get("search"), type_filter=p.get("type"))


class PayableEntityRetrieveView(generics.RetrieveAPIView):
    permission_classes = [IsAdminOrSuperuser]
    serializer_class   = PayableEntityReadSerializer

    def get_object(self):
        return get_payable_entity_by_id(self.kwargs["pk"])


class PayableEntityStatsView(APIView):
    permission_classes = [IsAdminOrSuperuser]

    def get(self, request, pk):
        entity = get_payable_entity_by_id(pk)
        return Response(PayableEntityStatsSerializer(get_payable_entity_stats(entity)).data)


class PayableEntityDeleteView(APIView):
    permission_classes = [IsAdminOrSuperuser]

    def delete(self, request, pk):
        delete_payable_entity(pk=pk, user=request.user)
        return Response({"detail": "Record deleted."}, status=status.HTTP_200_OK)


class PayableEntityPaymentListView(generics.ListAPIView):
    """GET /manufacturing-costs/payable-entities/<pk>/payments/ — this entity's own payment history."""
    permission_classes = [IsAdminOrSuperuser]
    serializer_class   = PaymentReadSerializer

    def get_queryset(self):
        return get_payments_for_entity(self.kwargs["pk"], search=self.request.query_params.get("search"))


# ---------------------------------------------------------------------------
# Page 4 (record) / Page 5 (all payments)
# ---------------------------------------------------------------------------

class PaymentListCreateView(AllocationsListMixin, generics.ListCreateAPIView):
    """Filter params for GET: search (reference number), entity_id, entity_type, date, date_from, date_to"""
    permission_classes = [IsAdminOrSuperuser]
    allocations_source_model = "manufacturing_costs.payment"
    allocations_context_key  = "manufacturing_costs_payment_allocations"

    def get_serializer_class(self):
        return PaymentWriteSerializer if self.request.method == "POST" else PaymentReadSerializer

    def get_queryset(self):
        p = self.request.query_params
        return get_all_payments(
            search=p.get("search"), entity_id=p.get("entity_id"), entity_type=p.get("entity_type"),
            date=p.get("date"), date_from=p.get("date_from"), date_to=p.get("date_to"),
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        obj = create_payment(
            entity_id=d["entity_id"], amount=d["amount"], payment_date=d["payment_date"],
            note=d.get("note", ""), method_allocations=as_splits(d["method_allocations"]), user=request.user,
        )
        return Response(PaymentReadSerializer(obj).data, status=status.HTTP_201_CREATED)


class PaymentRetrieveDestroyView(generics.RetrieveDestroyAPIView):
    permission_classes = [IsAdminOrSuperuser]
    serializer_class   = PaymentReadSerializer

    def get_object(self):
        return get_payment_by_id(self.kwargs["pk"])

    def destroy(self, request, *args, **kwargs):
        delete_payment(pk=self.kwargs["pk"], user=request.user)
        return Response({"detail": "Payment deleted and cash-in-hand restored."}, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Page 1 — Overview stats
# ---------------------------------------------------------------------------

class ManufacturingCostsStatsView(APIView):
    """GET /manufacturing-costs/stats/ — one singleton read, O(1)."""
    permission_classes = [IsAdminOrSuperuser]

    def get(self, request):
        return Response(ManufacturingCostsStatsSerializer(get_manufacturing_costs_stats()).data, status=status.HTTP_200_OK)
