from django.db.models import F, Prefetch, QuerySet
from django.shortcuts import get_object_or_404

from backend.search import search_q

from ..models import (
    CuttingBreakdownItem, CuttingBreakdownItemShelfAllocation, CuttingIssuedMaterial,
    CuttingMaterialConsumption, CuttingMaterialShelfDraw, Recipe, WipProduct,
)
from ..utils import WIP_PRODUCT_SELECT_RELATED


def _clean(value):
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped if stripped else None


# ---------------------------------------------------------------------------
# Issuable WIP cores — whole Rewound Cores only (stage="rewinding"), never
# an already-Cut Piece. available_quantity is the live WipInventory figure;
# NOTE this can overstate what's actually issuable, since some of that
# quantity may belong to a Rewinding batch that hasn't finished yet (cost
# unknown) — issue_cutting_material's FIFO walk is the trustworthy check.
# ---------------------------------------------------------------------------

def get_issuable_wip_cores(*, search: str = None) -> QuerySet:
    qs = (
        WipProduct.objects.select_related("family", "binding", "yard", "length_mm", "inventory")
        .filter(is_deleted=False, stage=WipProduct.Stage.REWINDING)
        .annotate(available_quantity=F("inventory__quantity"))
    )
    if _clean(search):
        qs = qs.filter(search_q(_clean(search), "name"))
    return qs


def get_available_wip_batches_for_fifo(wip_product_id: int, *, for_update: bool = False) -> QuerySet:
    """
    WIP-equivalent of purchases.selectors.get_available_purchase_items_for_fifo
    — RecipeBreakdownItem rows (from FINISHED Rewinding recipes only, so cost
    is known) with remaining stock, oldest-finished-first.
    """
    from ..models import RecipeBreakdownItem

    qs = (
        RecipeBreakdownItem.objects
        .filter(
            wip_product_id=wip_product_id,
            is_deleted=False,
            recipe__status=Recipe.Status.FINISHED,
            remaining_quantity__gt=0,
        )
        .order_by("recipe__finished_at", "pk")
    )
    if for_update:
        qs = qs.select_for_update()
    return qs


# ---------------------------------------------------------------------------
# Cutting Recipe detail — separate prefetch builder from Rewinding's
# _recipe_qs (different child models), same shape/reasoning.
# ---------------------------------------------------------------------------

def _cutting_recipe_qs():
    return Recipe.objects.select_related(
        "created_by", "updated_by", "finished_by",
    ).prefetch_related(
        Prefetch(
            "cutting_issued_material",
            queryset=CuttingIssuedMaterial.objects.select_related("wip_product").prefetch_related(
                Prefetch(
                    "consumptions",
                    queryset=CuttingMaterialConsumption.objects.select_related(
                        "wip_batch", "wip_batch__wip_product", "wip_batch__recipe",
                    ),
                ),
                Prefetch(
                    "shelf_draws",
                    queryset=CuttingMaterialShelfDraw.objects.select_related("shelf"),
                ),
            ),
        ),
        Prefetch(
            "cutting_breakdown_items",
            queryset=CuttingBreakdownItem.objects.select_related(
                *[f"wip_product__{f}" for f in WIP_PRODUCT_SELECT_RELATED], "wip_product",
            ).prefetch_related(
                Prefetch(
                    "shelf_allocations",
                    queryset=CuttingBreakdownItemShelfAllocation.objects.select_related("shelf"),
                ),
            ),
        ),
    )


def get_cutting_recipe_by_id(pk: int) -> Recipe:
    return get_object_or_404(
        _cutting_recipe_qs(), pk=pk, is_deleted=False, recipe_type=Recipe.RecipeType.CUTTING,
    )


def get_all_cutting_recipes(*, status: str = None, search: str = None) -> QuerySet:
    qs = _cutting_recipe_qs().filter(is_deleted=False, recipe_type=Recipe.RecipeType.CUTTING)
    if _clean(status):
        qs = qs.filter(status=_clean(status))
    if _clean(search):
        qs = qs.filter(search_q(_clean(search), "recipe_number", "name"))
    return qs


def get_cutting_issued_material(*, recipe_id: int) -> CuttingIssuedMaterial:
    # wip_product__length_mm: finish_cutting_recipe reads
    # issued.wip_product.length_mm.value to compute total_issued_length_mm.
    return get_object_or_404(
        CuttingIssuedMaterial.objects.select_related("recipe", "wip_product", "wip_product__length_mm"),
        recipe_id=recipe_id,
    )
