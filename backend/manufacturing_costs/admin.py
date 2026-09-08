from django.contrib import admin

from .models import (
    Employee, FactoryOverheadSetting, Machine, ManufacturingCostsFlow,
    PayableEntity, PayableEntityMonthlySnapshot, Payment,
)


class AuditAdminMixin:
    def save_model(self, request, obj, form, change):
        if not change and hasattr(obj, "created_by"):
            obj.created_by = request.user
        if hasattr(obj, "updated_by"):
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)


class SoftDeleteAdminMixin:
    list_select_related = ()

    def get_queryset(self, request):
        qs = self.model.objects.all()
        if self.list_select_related:
            qs = qs.select_related(*self.list_select_related)
        return qs


@admin.register(Employee)
class EmployeeAdmin(AuditAdminMixin, SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display    = ["name", "monthly_salary", "rate_per_hour", "is_deleted"]
    list_filter     = ["is_deleted"]
    search_fields   = ["name"]
    readonly_fields = ["rate_per_hour"]


@admin.register(Machine)
class MachineAdmin(AuditAdminMixin, SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display    = ["name", "category", "monthly_repair_cost", "rate_per_hour", "is_deleted"]
    list_filter     = ["is_deleted", "category"]
    search_fields   = ["name"]
    readonly_fields = ["rate_per_hour"]


@admin.register(FactoryOverheadSetting)
class FactoryOverheadSettingAdmin(admin.ModelAdmin):
    list_display = ["rent_amount", "electricity_amount", "updated_at"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PayableEntity)
class PayableEntityAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display        = ["__str__", "type", "overall_total_paid", "overall_payment_count", "is_deleted"]
    list_filter          = ["is_deleted", "type"]
    list_select_related  = ("employee", "machine")


@admin.register(PayableEntityMonthlySnapshot)
class PayableEntityMonthlySnapshotAdmin(admin.ModelAdmin):
    list_display        = ["entity", "period", "total_paid"]
    list_filter          = ["period"]
    list_select_related  = ("entity",)


@admin.register(ManufacturingCostsFlow)
class ManufacturingCostsFlowAdmin(admin.ModelAdmin):
    list_display = ["snapshots_caught_up_through", "last_updated_at"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(AuditAdminMixin, SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display        = ["reference_number", "entity", "amount", "payment_date", "is_deleted"]
    list_filter          = ["is_deleted"]
    search_fields        = ["reference_number"]
    list_select_related  = ("entity",)
    readonly_fields      = ["reference_number"]
