from django.contrib import admin

from .models import (
    CuttingBreakdownItem, CuttingIssuedMaterial, CuttingMaterialConsumption, FgProduct,
    PackingIssuedMaterial, PackingIssuedPiece, PackingMaterialConsumption, PackingOutputItem,
    PackingPieceConsumption, Recipe, RecipeBreakdownItem, RecipeIssuedMaterial, RecipeLabor,
    RecipeMachine, RecipeMaterialConsumption, RewoundCoreBinding, RewoundCoreLengthMm,
    RewoundCoreYard, WipProduct,
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
    list_display        = ["name", "code", "family", "stage", "is_deleted", "created_at"]
    list_filter         = ["is_deleted", "stage", "family"]
    search_fields       = ["name", "code"]
    list_select_related = ("family",)
    readonly_fields     = AuditAdminMixin.readonly_fields + ("code", "variant_key")


@admin.register(FgProduct)
class FgProductAdmin(AuditAdminMixin, SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display        = ["name", "code", "is_deleted", "created_at"]
    list_filter         = ["is_deleted"]
    search_fields       = ["name", "code"]
    readonly_fields     = AuditAdminMixin.readonly_fields + ("code", "variant_key")


class RecipeIssuedMaterialInline(admin.TabularInline):
    model    = RecipeIssuedMaterial
    extra    = 0
    readonly_fields = ("kind", "product", "quantity")
    can_delete = False


class RecipeBreakdownItemInline(admin.TabularInline):
    model    = RecipeBreakdownItem
    extra    = 0
    readonly_fields = ("wip_product", "quantity", "remaining_quantity", "unit_cost_snapshot", "full_unit_cost_snapshot")
    can_delete = False


class RecipeLaborInline(admin.TabularInline):
    model      = RecipeLabor
    extra      = 0
    readonly_fields = ("employee", "rate_per_hour_snapshot", "created_at")
    can_delete = True


class RecipeMachineInline(admin.TabularInline):
    model      = RecipeMachine
    extra      = 0
    readonly_fields = ("machine", "rate_per_hour_snapshot", "created_at")
    can_delete = True


class CuttingIssuedMaterialInline(admin.TabularInline):
    model      = CuttingIssuedMaterial
    extra      = 0
    readonly_fields = ("wip_product", "quantity")
    can_delete = False


class CuttingBreakdownItemInline(admin.TabularInline):
    model      = CuttingBreakdownItem
    extra      = 0
    readonly_fields = ("wip_product", "length_mm", "quantity", "remaining_quantity",
                        "unit_cost_before_waste", "unit_cost_snapshot", "full_unit_cost_snapshot")
    can_delete = False


class PackingIssuedPieceInline(admin.TabularInline):
    model      = PackingIssuedPiece
    extra      = 0
    readonly_fields = ("wip_product", "quantity")
    can_delete = False


class PackingIssuedMaterialInline(admin.TabularInline):
    model      = PackingIssuedMaterial
    extra      = 0
    readonly_fields = ("product", "quantity")
    can_delete = False


class PackingOutputItemInline(admin.TabularInline):
    model      = PackingOutputItem
    extra      = 0
    readonly_fields = ("fg_product", "quantity", "remaining_quantity", "unit_cost_snapshot", "full_unit_cost_snapshot")
    can_delete = False


@admin.register(Recipe)
class RecipeAdmin(AuditAdminMixin, SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display        = ["recipe_number", "name", "recipe_type", "status", "cost_per_unit", "full_cost_per_unit", "waste_length_mm", "created_at"]
    list_filter         = ["is_deleted", "recipe_type", "status"]
    search_fields       = ["recipe_number", "name"]
    readonly_fields     = AuditAdminMixin.readonly_fields + (
        "recipe_number", "cost_per_unit", "full_cost_per_unit", "waste_length_mm", "waste_cost",
        "finished_by", "finished_at",
    )
    # Rewinding, Cutting, and Packing inlines are all registered here since
    # Recipe is the shared header — only one set is ever populated per row,
    # per recipe_type, so the others simply show empty. Labor/Machine
    # inlines apply to every recipe_type (shared DL+FOH mechanism).
    inlines             = [
        RecipeIssuedMaterialInline, RecipeBreakdownItemInline,
        CuttingIssuedMaterialInline, CuttingBreakdownItemInline,
        PackingIssuedPieceInline, PackingIssuedMaterialInline, PackingOutputItemInline,
        RecipeLaborInline, RecipeMachineInline,
    ]


@admin.register(RecipeMaterialConsumption)
class RecipeMaterialConsumptionAdmin(admin.ModelAdmin):
    list_display        = ["issued_material", "purchase_item", "quantity", "unit_cost", "created_at"]
    list_select_related = ("issued_material", "purchase_item")


@admin.register(CuttingMaterialConsumption)
class CuttingMaterialConsumptionAdmin(admin.ModelAdmin):
    list_display        = ["issued_material", "wip_batch", "quantity", "unit_cost", "created_at"]
    list_select_related = ("issued_material", "wip_batch")


@admin.register(PackingPieceConsumption)
class PackingPieceConsumptionAdmin(admin.ModelAdmin):
    list_display        = ["issued_material", "piece_batch", "quantity", "unit_cost", "created_at"]
    list_select_related = ("issued_material", "piece_batch")


@admin.register(PackingMaterialConsumption)
class PackingMaterialConsumptionAdmin(admin.ModelAdmin):
    list_display        = ["issued_material", "purchase_item", "quantity", "unit_cost", "created_at"]
    list_select_related = ("issued_material", "purchase_item")
