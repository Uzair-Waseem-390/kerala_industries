"""
Shared select_related path list for WipProduct — used by both rewinding.py
and cutting.py selectors wherever a queryset feeds WipProductReadSerializer
(directly, or nested under a breakdown item).

WipProductReadSerializer nests RewoundCoreBindingReadSerializer/
YardReadSerializer/LengthMmReadSerializer, each of which extends
AuditReadMixin (created_by/updated_by StringRelatedFields) — found via a
query-count check while verifying Cutting (2026-09): selecting only
"binding"/"yard"/"length_mm" themselves covers the object, but not THEIR
own created_by/updated_by, so every WipProduct row serialized fired up to
6 extra queries (one per nested attribute's created_by/updated_by). Same
gap existed in the WIP Products list, WIP Inventory list, and the
Rewinding recipe detail endpoint — not just the new Cutting one.
"""
WIP_PRODUCT_SELECT_RELATED = (
    "family",
    "binding", "binding__created_by", "binding__updated_by",
    "yard", "yard__created_by", "yard__updated_by",
    "length_mm", "length_mm__created_by", "length_mm__updated_by",
    "created_by", "updated_by",
)


def get_candidate_shelves_for_wip_product(wip_product_id: int, *, search: str = None):
    """
    WIP-equivalent of purchases.selectors.get_candidate_shelves_for_product
    — shelves that currently hold stock (quantity > 0) of a given WIP
    product, for the consumption-side shelf picker (issuing a WIP core into
    a Cutting recipe, or increasing an already-issued quantity). Mirrors
    the RM version exactly, pointed at WipShelfStock via Shelf's
    "wip_stock_rows" related_name instead of RM's "stock_rows".
    """
    from django.db.models import Sum

    from backend.search import search_q
    from purchases.models import Shelf
    from purchases.selectors import _clean

    qs = Shelf.objects.filter(
        is_deleted=False, wip_stock_rows__product_id=wip_product_id, wip_stock_rows__quantity__gt=0,
    )
    if _clean(search):
        qs = qs.filter(search_q(_clean(search), "name"))
    return qs.annotate(
        available_quantity=Sum("wip_stock_rows__quantity")
    ).order_by("name")
