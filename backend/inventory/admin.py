from django.contrib import admin

from .models import Inventory


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display  = ["product", "quantity", "last_updated_by", "last_updated_at"]
    search_fields = ["product__name", "product__code"]
    readonly_fields = ["quantity", "last_updated_at", "last_updated_by"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
