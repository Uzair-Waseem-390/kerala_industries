from django.contrib import admin

from .models import (
    Recipe, RecipeBreakdownItem, RecipeIssuedMaterial, RecipeMaterialConsumption,
    RewoundCoreBinding, RewoundCoreLengthMm, RewoundCoreYard,
    WipInventory, WipProduct, WipShelfStock, WipShelfStockMovement,
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
    list_select_related = ()

    def get_queryset(self, request):
        qs = self.model.all_objects.all()
        if self.list_select_related:
            qs = qs.select_related(*self.list_select_related)
        return qs


class _LookupAdmin(AuditAdminMixin, SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display    = ["value", "is_deleted", "created_by", "created_at"]
    list_filter     = ["is_deleted"]
    search_fields   = ["value"]
    readonly_fields = AuditAdminMixin.readonly_fields


@admin.register(RewoundCoreBinding)
class RewoundCoreBindingAdmin(_LookupAdmin):
    pass


@admin.register(RewoundCoreYard)
class RewoundCoreYardAdmin(_LookupAdmin):
    pass


@admin.register(RewoundCoreLengthMm)
class RewoundCoreLengthMmAdmin(_LookupAdmin):
    pass


@admin.register(WipProduct)
class WipProductAdmin(AuditAdminMixin, SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display        = ["name", "family", "is_deleted", "created_at"]
    list_filter         = ["is_deleted", "family"]
    search_fields       = ["name"]
    list_select_related = ("family",)
    readonly_fields     = AuditAdminMixin.readonly_fields + ("variant_key",)


@admin.register(WipInventory)
class WipInventoryAdmin(admin.ModelAdmin):
    list_display        = ["product", "quantity", "last_updated_at"]
    search_fields       = ["product__name"]
    list_select_related = ("product",)


@admin.register(WipShelfStock)
class WipShelfStockAdmin(admin.ModelAdmin):
    list_display        = ["shelf", "product", "quantity", "last_updated_at"]
    search_fields       = ["shelf__name", "product__name"]
    list_select_related = ("shelf", "product")


@admin.register(WipShelfStockMovement)
class WipShelfStockMovementAdmin(admin.ModelAdmin):
    list_display        = ["shelf", "product", "delta", "reason", "reference", "created_at"]
    list_filter         = ["reason"]
    search_fields       = ["shelf__name", "product__name", "reference"]
    list_select_related = ("shelf", "product")


class RecipeIssuedMaterialInline(admin.TabularInline):
    model    = RecipeIssuedMaterial
    extra    = 0
    readonly_fields = ("kind", "product", "quantity")
    can_delete = False


class RecipeBreakdownItemInline(admin.TabularInline):
    model    = RecipeBreakdownItem
    extra    = 0
    readonly_fields = ("wip_product", "quantity", "remaining_quantity", "unit_cost_snapshot")
    can_delete = False


@admin.register(Recipe)
class RecipeAdmin(AuditAdminMixin, SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display        = ["recipe_number", "name", "recipe_type", "status", "cost_per_unit", "created_at"]
    list_filter         = ["is_deleted", "recipe_type", "status"]
    search_fields       = ["recipe_number", "name"]
    readonly_fields     = AuditAdminMixin.readonly_fields + ("recipe_number", "cost_per_unit", "finished_by", "finished_at")
    inlines             = [RecipeIssuedMaterialInline, RecipeBreakdownItemInline]


@admin.register(RecipeMaterialConsumption)
class RecipeMaterialConsumptionAdmin(admin.ModelAdmin):
    list_display        = ["issued_material", "purchase_item", "quantity", "unit_cost", "created_at"]
    list_select_related = ("issued_material", "purchase_item")
