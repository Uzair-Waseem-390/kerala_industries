from django.contrib import admin

from .models import Inventory, WipInventory, WipShelfStock, WipShelfStockMovement


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display  = ["product", "quantity", "last_updated_by", "last_updated_at"]
    search_fields = ["product__name", "product__code"]
    readonly_fields = ["quantity", "last_updated_at", "last_updated_by"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# WipInventory / WipShelfStock / WipShelfStockMovement — moved here from
# production/admin.py (2026-09), alongside the models themselves.

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
