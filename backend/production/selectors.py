from django.db.models import Prefetch, QuerySet
from django.shortcuts import get_object_or_404

from backend.search import search_q

from .models import (
    Recipe, RecipeBreakdownItem, RecipeIssuedMaterial, RecipeMaterialConsumption,
    RewoundCoreBinding, RewoundCoreLengthMm, RewoundCoreYard,
    WipInventory, WipProduct, WipShelfStock,
)


def _clean(value):
    """Returns None if value is None or empty/whitespace string, else stripped value."""
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped if stripped else None


# ---------------------------------------------------------------------------
# WIP attribute lookups (Rewinding)
# ---------------------------------------------------------------------------

def get_all_rewound_core_bindings():
    return RewoundCoreBinding.objects.select_related("created_by", "updated_by").filter(is_deleted=False)

def get_rewound_core_binding_by_id(pk: int) -> RewoundCoreBinding:
    return get_object_or_404(RewoundCoreBinding, pk=pk, is_deleted=False)


def get_all_rewound_core_yards():
    return RewoundCoreYard.objects.select_related("created_by", "updated_by").filter(is_deleted=False)

def get_rewound_core_yard_by_id(pk: int) -> RewoundCoreYard:
    return get_object_or_404(RewoundCoreYard, pk=pk, is_deleted=False)


def get_all_rewound_core_length_mms():
    return RewoundCoreLengthMm.objects.select_related("created_by", "updated_by").filter(is_deleted=False)

def get_rewound_core_length_mm_by_id(pk: int) -> RewoundCoreLengthMm:
    return get_object_or_404(RewoundCoreLengthMm, pk=pk, is_deleted=False)


# ---------------------------------------------------------------------------
# WIP Product / Inventory
# ---------------------------------------------------------------------------

_WIP_PRODUCT_RELATED = ("family", "binding", "yard", "length_mm", "created_by", "updated_by")

def get_all_wip_products(*, search: str = None) -> QuerySet:
    qs = WipProduct.objects.select_related(*_WIP_PRODUCT_RELATED).filter(is_deleted=False)
    if _clean(search):
        qs = qs.filter(search_q(_clean(search), "name"))
    return qs

def get_wip_product_by_id(pk: int) -> WipProduct:
    return get_object_or_404(WipProduct.objects.select_related(*_WIP_PRODUCT_RELATED), pk=pk, is_deleted=False)


def get_all_wip_inventory(*, search: str = None) -> QuerySet:
    qs = WipInventory.objects.select_related(*[f"product__{f}" for f in _WIP_PRODUCT_RELATED], "product")
    if _clean(search):
        qs = qs.filter(search_q(_clean(search), "product__name"))
    return qs


# ---------------------------------------------------------------------------
# Recipe
# ---------------------------------------------------------------------------

def _recipe_qs():
    return Recipe.objects.select_related(
        "created_by", "updated_by", "finished_by",
    ).prefetch_related(
        Prefetch(
            "issued_materials",
            queryset=RecipeIssuedMaterial.objects.select_related("product").prefetch_related(
                Prefetch(
                    "consumptions",
                    queryset=RecipeMaterialConsumption.objects.select_related("purchase_item", "purchase_item__product"),
                ),
            ),
        ),
        Prefetch(
            "breakdown_items",
            queryset=RecipeBreakdownItem.objects.select_related(
                "wip_product", "wip_product__binding", "wip_product__yard", "wip_product__length_mm",
                "wip_product__created_by", "wip_product__updated_by",
            ),
        ),
    )


def get_all_recipes(*, status: str = None, search: str = None) -> QuerySet:
    qs = _recipe_qs().filter(is_deleted=False)
    if _clean(status):
        qs = qs.filter(status=_clean(status))
    if _clean(search):
        qs = qs.filter(search_q(_clean(search), "recipe_number", "name"))
    return qs


def get_recipe_by_id(pk: int) -> Recipe:
    return get_object_or_404(_recipe_qs(), pk=pk, is_deleted=False)


def get_issued_material(*, recipe_id: int, kind: str) -> RecipeIssuedMaterial:
    return get_object_or_404(
        RecipeIssuedMaterial.objects.select_related("recipe", "product"),
        recipe_id=recipe_id, kind=kind,
    )


# ---------------------------------------------------------------------------
# RM products issuable into a recipe — already-purchased Jumbo/Cores
# variants, filtered by which anchor they trace back to.
# ---------------------------------------------------------------------------

def get_issuable_products(*, kind: str, search: str = None) -> QuerySet:
    from django.db.models import F
    from purchases.models import CORES_PRODUCT_CODE, JUMBO_PRODUCT_CODE, Product

    code = JUMBO_PRODUCT_CODE if kind == "jumbo" else CORES_PRODUCT_CODE
    qs = (
        Product.objects.select_related("family", "inventory")
        .filter(is_deleted=False, base_product__code=code)
        .annotate(available_quantity=F("inventory__quantity"))
    )
    if _clean(search):
        qs = qs.filter(search_q(_clean(search), "name", "code"))
    return qs
