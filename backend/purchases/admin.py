from django.contrib import admin

from .models import (
    CartonSize, CoreLength, CoreThickness, JumboBinding, JumboName,
    LostInventoryFIFOConsumption, LostInventoryItem,
    LostInventoryRecord, PackingSize, Product, PurchaseItem, PurchaseOrder,
    PurchaseReturn, PurchaseReturnItem, SavedPurchaseOrderPDF,
    Shelf, Supplier, SupplierPayment,
)


class AuditAdminMixin:
    readonly_fields = (
        "created_by", "updated_by", "deleted_by",
        "created_at", "updated_at", "deleted_at",
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


class SoftDeleteAdminMixin:
    # Set on a subclass to select_related() the FK columns shown in
    # list_display — avoids Django admin's default one-query-per-row-per-FK
    # N+1 on the changelist. Optional/low-priority (superuser-only backoffice
    # tool, not a production hot path), but free to add where the FK is
    # already known from list_display.
    list_select_related = ()

    def get_queryset(self, request):
        qs = self.model.all_objects.all()
        if self.list_select_related:
            qs = qs.select_related(*self.list_select_related)
        return qs


class _LookupAdmin(AuditAdminMixin, SoftDeleteAdminMixin, admin.ModelAdmin):
    """Shared changelist config for the six id+value attribute lookups below."""
    list_display    = ["value", "is_deleted", "created_by", "created_at"]
    list_filter     = ["is_deleted"]
    search_fields   = ["value"]
    readonly_fields = AuditAdminMixin.readonly_fields


@admin.register(JumboName)
class JumboNameAdmin(_LookupAdmin):
    pass


@admin.register(JumboBinding)
class JumboBindingAdmin(_LookupAdmin):
    pass


@admin.register(CoreLength)
class CoreLengthAdmin(_LookupAdmin):
    pass


@admin.register(CoreThickness)
class CoreThicknessAdmin(_LookupAdmin):
    pass


@admin.register(PackingSize)
class PackingSizeAdmin(_LookupAdmin):
    pass


@admin.register(CartonSize)
class CartonSizeAdmin(_LookupAdmin):
    pass


@admin.register(Shelf)
class ShelfAdmin(AuditAdminMixin, SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display  = ["name", "is_deleted", "created_by", "created_at"]
    list_filter   = ["is_deleted"]
    search_fields = ["name"]
    readonly_fields = AuditAdminMixin.readonly_fields


@admin.register(Supplier)
class SupplierAdmin(AuditAdminMixin, SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display  = ["name", "code", "is_deleted", "created_by", "created_at"]
    list_filter   = ["is_deleted"]
    search_fields = ["name", "code"]
    readonly_fields = AuditAdminMixin.readonly_fields


@admin.register(Product)
class ProductAdmin(AuditAdminMixin, SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display  = ["name", "code", "is_deleted", "created_by", "created_at"]
    list_filter   = ["is_deleted"]
    search_fields = ["name", "code"]
    readonly_fields = AuditAdminMixin.readonly_fields


class PurchaseItemInline(admin.TabularInline):
    model         = PurchaseItem
    extra         = 0
    readonly_fields = [
        "gross_amount", "gst_amount", "wht_amount",
        "total_price", "remaining_quantity", "returned_quantity",
    ]
    can_delete = False


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(AuditAdminMixin, SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display  = [
        "order_number", "supplier", "status", "payment_type",
        "net_payable", "payable_outstanding", "payment_status",
        "is_deleted", "created_at",
    ]
    list_filter   = ["status", "payment_type", "payment_status", "is_deleted"]
    search_fields = ["order_number", "supplier__name", "supplier__code"]
    readonly_fields = AuditAdminMixin.readonly_fields + (
        "order_number", "status", "confirmed_by", "confirmed_at",
        "gross_amount", "gst_total", "wht_total", "net_payable",
        "payable_outstanding", "total_paid", "payment_status", "payment_type",
    )
    inlines = [PurchaseItemInline]
    list_select_related = ["supplier"]


@admin.register(SupplierPayment)
class SupplierPaymentAdmin(AuditAdminMixin, SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display  = ["order", "amount", "method", "payment_date", "is_deleted"]
    list_filter   = ["method", "is_deleted"]
    search_fields = ["order__order_number", "order__supplier__name"]
    readonly_fields = AuditAdminMixin.readonly_fields
    list_select_related = ["order"]


class PurchaseReturnItemInline(admin.TabularInline):
    model         = PurchaseReturnItem
    extra         = 0
    readonly_fields = [
        "unit_price", "gross_amount", "gst_amount", "wht_amount", "total_amount",
    ]
    can_delete = False


@admin.register(PurchaseReturn)
class PurchaseReturnAdmin(AuditAdminMixin, SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display  = [
        "order", "status", "total_return_amount",
        "accepted_by", "accepted_at", "created_at",
    ]
    list_filter   = ["status"]
    search_fields = ["order__order_number", "order__supplier__name"]
    readonly_fields = AuditAdminMixin.readonly_fields + (
        "status", "accepted_by", "accepted_at",
        "total_return_gross", "total_return_gst",
        "total_return_wht", "total_return_amount",
    )
    inlines = [PurchaseReturnItemInline]
    list_select_related = ["order"]


class LostInventoryItemInline(admin.TabularInline):
    model         = LostInventoryItem
    extra         = 0
    readonly_fields = ["unit_cost", "total_cost", "found_quantity"]
    can_delete = False


@admin.register(LostInventoryRecord)
class LostInventoryRecordAdmin(AuditAdminMixin, SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display  = ["reference_number", "total_lost_amount", "created_by", "created_at", "is_deleted"]
    list_filter   = ["is_deleted"]
    search_fields = ["reference_number"]
    readonly_fields = AuditAdminMixin.readonly_fields + ("reference_number", "total_lost_amount")
    inlines = [LostInventoryItemInline]


@admin.register(LostInventoryFIFOConsumption)
class LostInventoryFIFOConsumptionAdmin(admin.ModelAdmin):
    list_display  = [
        "lost_item", "purchase_item", "quantity",
        "unit_cost", "restored_quantity",
    ]
    search_fields = [
        "lost_item__product__name", "lost_item__product__code",
        "purchase_item__product__name",
    ]
    readonly_fields = [
        "lost_item", "purchase_item", "quantity",
        "unit_cost", "restored_quantity",
    ]




@admin.register(SavedPurchaseOrderPDF)
class SavedPurchaseOrderPDFAdmin(admin.ModelAdmin):
    list_display  = ["order", "file_name", "saved_by", "is_deleted", "created_at"]
    list_filter   = ["is_deleted"]
    search_fields = ["order__order_number", "file_name"]
    readonly_fields = ["order", "file_name", "file_path", "saved_by", "deleted_by", "created_at", "deleted_at"]

    def has_add_permission(self, request):
        return False


# InventoryAdmin moved to inventory/admin.py — mechanical extraction.