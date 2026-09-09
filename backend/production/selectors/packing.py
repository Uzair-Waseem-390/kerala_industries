from django.db.models import F, Prefetch, QuerySet
from django.shortcuts import get_object_or_404

from backend.search import search_q

from ..models import (
    CuttingBreakdownItem, FgProduct, PackingIssuedMaterial, PackingIssuedPiece, PackingMaterialConsumption,
    PackingMaterialShelfDraw, PackingOutputItem, PackingOutputShelfAllocation, PackingPieceConsumption,
    PackingPieceShelfDraw, Recipe, RecipeLabor, RecipeMachine, WipProduct,
)
from ..utils import FG_PRODUCT_SELECT_RELATED, WIP_PRODUCT_SELECT_RELATED


def _clean(value):
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped if stripped else None


# ---------------------------------------------------------------------------
# Issuable Cut Pieces — WipProduct rows at stage="cutting" only, never a
# whole Rewound Core. Mirrors get_issuable_wip_cores exactly, one stage over.
# ---------------------------------------------------------------------------

def get_issuable_cutting_pieces(*, search: str = None) -> QuerySet:
    qs = (
        WipProduct.objects.select_related("family", "binding", "yard", "length_mm", "inventory")
        .filter(is_deleted=False, stage=WipProduct.Stage.CUTTING)
        .annotate(available_quantity=F("inventory__quantity"))
    )
    if _clean(search):
        qs = qs.filter(search_q(_clean(search), "name"))
    return qs


def get_available_cutting_batches_for_fifo(wip_product_id: int, *, for_update: bool = False) -> QuerySet:
    """
    Packing-equivalent of get_available_wip_batches_for_fifo — CuttingBreakdownItem
    rows (from FINISHED Cutting recipes only, so cost is known) with remaining
    stock, oldest-finished-first.
    """
    qs = (
        CuttingBreakdownItem.objects
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
# Packing Recipe detail — separate prefetch builder from Rewinding/Cutting's
# (different child models), same shape/reasoning.
# ---------------------------------------------------------------------------

def _packing_recipe_qs():
    return Recipe.objects.select_related(
        "created_by", "updated_by", "finished_by",
    ).prefetch_related(
        Prefetch(
            "packing_issued_piece",
            queryset=PackingIssuedPiece.objects.select_related(
                *[f"wip_product__{f}" for f in WIP_PRODUCT_SELECT_RELATED], "wip_product",
            ).prefetch_related(
                Prefetch(
                    "consumptions",
                    queryset=PackingPieceConsumption.objects.select_related(
                        "piece_batch", "piece_batch__wip_product", "piece_batch__recipe",
                    ),
                ),
                Prefetch(
                    "shelf_draws",
                    queryset=PackingPieceShelfDraw.objects.select_related("shelf"),
                ),
            ),
        ),
        Prefetch(
            "packing_issued_material",
            queryset=PackingIssuedMaterial.objects.select_related("product").prefetch_related(
                Prefetch(
                    "consumptions",
                    queryset=PackingMaterialConsumption.objects.select_related("purchase_item", "purchase_item__product"),
                ),
                Prefetch(
                    "shelf_draws",
                    queryset=PackingMaterialShelfDraw.objects.select_related("shelf"),
                ),
            ),
        ),
        Prefetch(
            "packing_output_item",
            queryset=PackingOutputItem.objects.select_related(
                "fg_product", "fg_product__binding", "fg_product__yard", "fg_product__length_mm",
            ).prefetch_related(
                Prefetch(
                    "shelf_allocations",
                    queryset=PackingOutputShelfAllocation.objects.select_related("shelf"),
                ),
            ),
        ),
        Prefetch("labor_entries", queryset=RecipeLabor.objects.select_related("employee")),
        Prefetch("machine_entries", queryset=RecipeMachine.objects.select_related("machine")),
    )


def get_packing_recipe_by_id(pk: int) -> Recipe:
    return get_object_or_404(
        _packing_recipe_qs(), pk=pk, is_deleted=False, recipe_type=Recipe.RecipeType.PACKING,
    )


def get_all_packing_recipes(*, status: str = None, search: str = None) -> QuerySet:
    qs = _packing_recipe_qs().filter(is_deleted=False, recipe_type=Recipe.RecipeType.PACKING)
    if _clean(status):
        qs = qs.filter(status=_clean(status))
    if _clean(search):
        qs = qs.filter(search_q(_clean(search), "recipe_number", "name"))
    return qs


def get_packing_issued_piece(*, recipe_id: int) -> PackingIssuedPiece:
    return get_object_or_404(
        PackingIssuedPiece.objects.select_related("recipe", "wip_product"),
        recipe_id=recipe_id,
    )


def get_packing_issued_material(*, recipe_id: int) -> PackingIssuedMaterial:
    return get_object_or_404(
        PackingIssuedMaterial.objects.select_related("recipe", "product"),
        recipe_id=recipe_id,
    )


def get_fg_product_by_id(pk: int) -> FgProduct:
    return get_object_or_404(FgProduct.objects.select_related(*FG_PRODUCT_SELECT_RELATED), pk=pk, is_deleted=False)


def get_available_fg_batches_for_fifo(fg_product_id: int, *, for_update: bool = False) -> QuerySet:
    """
    FG-equivalent of get_available_wip_batches_for_fifo/get_available_cutting_batches_for_fifo
    — PackingOutputItem rows (from FINISHED Packing recipes — always true,
    PackingOutputItem is only ever created at finish_packing_recipe) with
    remaining stock, oldest-finished-first. FG's own FIFO cost layer, same
    role RecipeBreakdownItem/CuttingBreakdownItem play one stage earlier —
    lets Lost Inventory (and, eventually, a billing sale path) draw FG stock
    at its real locked-in cost instead of an average.
    """
    qs = (
        PackingOutputItem.objects
        .filter(fg_product_id=fg_product_id, is_deleted=False, remaining_quantity__gt=0)
        .order_by("recipe__finished_at", "pk")
    )
    if for_update:
        qs = qs.select_for_update()
    return qs
