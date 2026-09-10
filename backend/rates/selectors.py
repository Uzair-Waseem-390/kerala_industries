from decimal import Decimal

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import ProductRate, ProductRateHistory


# ---------------------------------------------------------------------------
# ProductRate selectors
# ---------------------------------------------------------------------------

def _clean(value):
    """Returns None if value is None or empty/whitespace, else stripped string."""
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


# ProductRateReadSerializer nests either the RM or FG product — everything
# here is serialized; without the user relations each row costs extra
# queries (N+1).
_RATE_RELATED = (
    "rm_product", "rm_product__created_by", "rm_product__updated_by",
    "rm_product__family", "rm_product__family__created_by", "rm_product__family__updated_by",
    "fg_product", "fg_product__created_by", "fg_product__updated_by",
    "fg_product__binding", "fg_product__yard", "fg_product__length_mm",
    "updated_by", "created_by",
)


def get_all_rates(
    *,
    search      : str = None,
    min_price   : str = None,
    max_price   : str = None,
) -> QuerySet:
    """
    Returns current active rates (Finished Goods + Cartons-family RM
    variants only — see purchases.selectors.is_cartons_product) with
    optional filtering and searching.

    Search  : product name or product code (case-insensitive, partial match)
    Filters : min/max selling price

    Ordered via Coalesce(fg_product__name, rm_product__name) instead of the
    old Meta.ordering="product__name" (no longer a single real column once
    `product` became a property over two nullable FKs).
    """
    from django.db.models import Q
    from django.db.models.functions import Coalesce

    from backend.search import search_q

    qs = ProductRate.objects.select_related(*_RATE_RELATED).filter(
        Q(rm_product__is_deleted=False) | Q(fg_product__is_deleted=False),
    )

    if _clean(search):
        qs = qs.filter(
            search_q(_clean(search), "rm_product__name", "rm_product__code")
            | search_q(_clean(search), "fg_product__name", "fg_product__code")
        )
    if _clean(min_price):
        qs = qs.filter(selling_price__gte=_clean(min_price))
    if _clean(max_price):
        qs = qs.filter(selling_price__lte=_clean(max_price))

    return qs.annotate(
        _name=Coalesce("fg_product__name", "rm_product__name"),
    ).order_by("_name")


def get_unpriced_products(*, search: str = None) -> list[dict]:
    """
    Products with no ProductRate yet — the "needs a price set" queue,
    restricted to Finished Goods + Cartons-family RM variants (the only
    products this app prices). Joins through UnpricedProduct (a
    materialized, explicitly-synced set — see rates.models.UnpricedProduct),
    not a live rate__isnull=True scan over the whole product catalog.

    Returns plain dicts (not a QuerySet) since the two halves come from two
    different model tables (purchases.Product / production.FgProduct) with
    no shared base — the serializer reads this shape directly.
    """
    from backend.search import search_q
    from production.models import FgProduct
    from purchases.models import CARTONS_PRODUCT_CODE, Product

    rm_qs = Product.objects.select_related(
        "created_by", "updated_by", "family", "family__created_by", "family__updated_by",
    ).filter(is_deleted=False, unpriced_entry__isnull=False, base_product__code=CARTONS_PRODUCT_CODE)
    fg_qs = FgProduct.objects.select_related(
        "created_by", "updated_by", "binding", "yard", "length_mm",
    ).filter(is_deleted=False, unpriced_entry__isnull=False)

    if _clean(search):
        rm_qs = rm_qs.filter(search_q(_clean(search), "name", "code"))
        fg_qs = fg_qs.filter(search_q(_clean(search), "name", "code"))

    rows = [
        {"id": p.id, "type": "rm", "name": p.name, "code": p.code, "product": p}
        for p in rm_qs
    ] + [
        {"id": p.id, "type": "fg", "name": p.name, "code": p.code, "product": p}
        for p in fg_qs
    ]
    rows.sort(key=lambda r: r["name"])
    return rows


def get_rate_by_id(pk: int) -> ProductRate:
    return get_object_or_404(
        ProductRate.objects.select_related(*_RATE_RELATED),
        pk=pk,
    )


def get_rate_by_product_id(*, rm_product_id: int = None, fg_product_id: int = None) -> ProductRate:
    if fg_product_id:
        return get_object_or_404(
            ProductRate.objects.select_related(*_RATE_RELATED),
            fg_product_id=fg_product_id, fg_product__is_deleted=False,
        )
    return get_object_or_404(
        ProductRate.objects.select_related(*_RATE_RELATED),
        rm_product_id=rm_product_id, rm_product__is_deleted=False,
    )


# ---------------------------------------------------------------------------
# ProductRateHistory selectors
# ---------------------------------------------------------------------------

def get_history_for_product(*, rm_product_id: int = None, fg_product_id: int = None) -> QuerySet:
    """Full price change log for a single product, newest first."""
    if fg_product_id:
        return ProductRateHistory.objects.select_related("fg_product", "changed_by").filter(fg_product_id=fg_product_id)
    return ProductRateHistory.objects.select_related("rm_product", "changed_by").filter(rm_product_id=rm_product_id)


def get_price_at_date(*, rm_product_id: int = None, fg_product_id: int = None, at: timezone.datetime) -> ProductRateHistory | None:
    """
    Returns the most recent history entry for a product at or before
    the given datetime. Used by billing to snapshot the correct price.
    Returns None if no price was set before that date.
    """
    qs = ProductRateHistory.objects.filter(changed_at__lte=at)
    qs = qs.filter(fg_product_id=fg_product_id) if fg_product_id else qs.filter(rm_product_id=rm_product_id)
    return qs.order_by("-changed_at").first()
