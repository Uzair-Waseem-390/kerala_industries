from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Recipe
from .permissions import IsAdminOrSuperuser
from .selectors import (
    get_all_cutting_recipes, get_all_fg_inventory, get_all_packing_recipes, get_all_recipes,
    get_all_rewound_core_bindings, get_all_rewound_core_length_mms, get_all_rewound_core_yards,
    get_all_wip_inventory, get_all_wip_products, get_candidate_shelves_for_fg_product,
    get_candidate_shelves_for_wip_product, get_cutting_recipe_by_id, get_fg_shelf_stock_rows,
    get_issuable_cutting_pieces, get_issuable_products, get_issuable_wip_cores,
    get_packing_recipe_by_id, get_recipe_by_id, get_rewound_core_binding_by_id,
    get_rewound_core_length_mm_by_id, get_rewound_core_yard_by_id, get_wip_product_by_id,
    get_wip_shelf_stock_rows,
)
from .serializers import (
    AddBreakdownItemSerializer, AddCuttingBreakdownItemSerializer, AddRecipeLaborSerializer,
    AddRecipeMachineSerializer, CandidateShelfSerializer, CreateCuttingRecipeSerializer,
    CreatePackingRecipeSerializer, CuttingRecipeReadSerializer, DeleteCuttingRecipeSerializer,
    DeletePackingRecipeSerializer, DeleteRecipeSerializer,
    FgInventoryReadSerializer, FgShelfStockReadSerializer, FinishPackingRecipeSerializer,
    IssuableCuttingPieceSerializer, IssuableProductSerializer, IssuableWipCoreSerializer,
    IssueCuttingMaterialSerializer, IssueMaterialSerializer, IssuePackingMaterialSerializer,
    IssuePackingPieceSerializer, PackingRecipeReadSerializer, RecipeCreateSerializer,
    RecipeReadSerializer, RewoundCoreBindingReadSerializer, RewoundCoreLengthMmReadSerializer,
    RewoundCoreYardReadSerializer, SetRecipeTimeSerializer, UpdateIssuedMaterialSerializer,
    UpdateRecipeDescriptionSerializer, UpdateRecipeNameSerializer, WipInventoryReadSerializer,
    WipProductReadSerializer, WipShelfStockReadSerializer,
)
from .services import (
    add_breakdown_item, add_cutting_breakdown_item, add_recipe_labor, add_recipe_machine,
    create_cutting_recipe, create_packing_recipe, create_recipe, delete_breakdown_item,
    delete_cutting_breakdown_item, delete_cutting_recipe, delete_packing_recipe, delete_recipe,
    finish_cutting_recipe, finish_packing_recipe, finish_recipe, issue_cutting_material,
    issue_material, issue_packing_material, issue_packing_piece, remove_recipe_labor,
    remove_recipe_machine, set_recipe_time, update_breakdown_item, update_cutting_breakdown_item,
    update_cutting_issued_material, update_issued_material, update_packing_issued_material,
    update_packing_issued_piece, update_recipe_description, update_recipe_name,
)


# ---------------------------------------------------------------------------
# WIP attribute lookups — read-only from the API (rows are system-derived)
# ---------------------------------------------------------------------------

class RewoundCoreBindingListView(generics.ListAPIView):
    permission_classes = [IsAdminOrSuperuser]
    serializer_class    = RewoundCoreBindingReadSerializer

    def get_queryset(self):
        return get_all_rewound_core_bindings()


class RewoundCoreBindingRetrieveView(generics.RetrieveAPIView):
    permission_classes = [IsAdminOrSuperuser]
    serializer_class    = RewoundCoreBindingReadSerializer

    def get_object(self):
        return get_rewound_core_binding_by_id(self.kwargs["pk"])


class RewoundCoreYardListView(generics.ListAPIView):
    permission_classes = [IsAdminOrSuperuser]
    serializer_class    = RewoundCoreYardReadSerializer

    def get_queryset(self):
        return get_all_rewound_core_yards()


class RewoundCoreYardRetrieveView(generics.RetrieveAPIView):
    permission_classes = [IsAdminOrSuperuser]
    serializer_class    = RewoundCoreYardReadSerializer

    def get_object(self):
        return get_rewound_core_yard_by_id(self.kwargs["pk"])


class RewoundCoreLengthMmListView(generics.ListAPIView):
    permission_classes = [IsAdminOrSuperuser]
    serializer_class    = RewoundCoreLengthMmReadSerializer

    def get_queryset(self):
        return get_all_rewound_core_length_mms()


class RewoundCoreLengthMmRetrieveView(generics.RetrieveAPIView):
    permission_classes = [IsAdminOrSuperuser]
    serializer_class    = RewoundCoreLengthMmReadSerializer

    def get_object(self):
        return get_rewound_core_length_mm_by_id(self.kwargs["pk"])


# ---------------------------------------------------------------------------
# WIP Product / Inventory — read-only
# ---------------------------------------------------------------------------

class WipProductListView(generics.ListAPIView):
    permission_classes = [IsAdminOrSuperuser]
    serializer_class    = WipProductReadSerializer

    def get_queryset(self):
        return get_all_wip_products(search=self.request.query_params.get("search"))


class WipProductRetrieveView(generics.RetrieveAPIView):
    permission_classes = [IsAdminOrSuperuser]
    serializer_class    = WipProductReadSerializer

    def get_object(self):
        return get_wip_product_by_id(self.kwargs["pk"])


class WipInventoryListView(generics.ListAPIView):
    permission_classes = [IsAdminOrSuperuser]
    serializer_class    = WipInventoryReadSerializer

    def get_queryset(self):
        return get_all_wip_inventory(
            search=self.request.query_params.get("search"),
            stage=self.request.query_params.get("stage"),
        )


class WipShelfStockListView(generics.ListAPIView):
    """GET /production/shelves/<pk>/wip-stock/ — WIP products + quantities on one shelf."""
    permission_classes = [IsAdminOrSuperuser]
    serializer_class    = WipShelfStockReadSerializer

    def get_queryset(self):
        from purchases.selectors import get_shelf_by_id
        get_shelf_by_id(self.kwargs["pk"])  # 404s if the shelf doesn't exist
        return get_wip_shelf_stock_rows(
            self.kwargs["pk"],
            search=self.request.query_params.get("search"),
            stage=self.request.query_params.get("stage"),
        )


# ---------------------------------------------------------------------------
# RM products issuable into a recipe
# ---------------------------------------------------------------------------

class IssuableProductListView(generics.ListAPIView):
    """GET /production/issuable-products/?kind=jumbo|cores&search=..."""
    permission_classes = [IsAdminOrSuperuser]
    serializer_class    = IssuableProductSerializer

    def get_queryset(self):
        kind = self.request.query_params.get("kind")
        if kind not in ("jumbo", "cores", "packing"):
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"kind": "kind must be 'jumbo', 'cores', or 'packing'."})
        return get_issuable_products(kind=kind, search=self.request.query_params.get("search"))


class IssuableWipCoreListView(generics.ListAPIView):
    """GET /production/issuable-wip-cores/?search=... — whole Rewound Cores only, for Cutting issuance."""
    permission_classes = [IsAdminOrSuperuser]
    serializer_class    = IssuableWipCoreSerializer

    def get_queryset(self):
        return get_issuable_wip_cores(search=self.request.query_params.get("search"))


class CandidateShelvesForWipProductListView(generics.ListAPIView):
    """
    GET /production/wip-shelves/candidates/?wip_product_id=<id>&search=...
    Shelves currently holding stock of a WIP product — the dropdown source
    for the consumption-side shelf picker (issuing a WIP core, or
    increasing an already-issued quantity). Mirrors
    purchases.CandidateShelvesForProductView.
    """
    permission_classes = [IsAdminOrSuperuser]
    serializer_class    = CandidateShelfSerializer

    def get_queryset(self):
        from rest_framework.exceptions import ValidationError
        wip_product_id = self.request.query_params.get("wip_product_id")
        if not wip_product_id:
            raise ValidationError({"wip_product_id": "This query parameter is required."})
        return get_candidate_shelves_for_wip_product(
            int(wip_product_id), search=self.request.query_params.get("search"),
        )


# ---------------------------------------------------------------------------
# Recipe
# ---------------------------------------------------------------------------

class RecipeListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminOrSuperuser]

    def get_serializer_class(self):
        return RecipeCreateSerializer if self.request.method == "POST" else RecipeReadSerializer

    def get_queryset(self):
        p = self.request.query_params
        return get_all_recipes(status=p.get("status"), search=p.get("search"))

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        recipe = create_recipe(
            name=d["name"], description=d.get("description", ""),
            recipe_type=d.get("recipe_type", "rewinding"), user=request.user,
        )
        return Response(RecipeReadSerializer(recipe).data, status=status.HTTP_201_CREATED)


class RecipeRetrieveView(generics.RetrieveDestroyAPIView):
    """
    DELETE reads a body (DeleteRecipeSerializer's shelf allocations for
    whichever materials were actually issued) — DRF parses a request body
    on DELETE the same as any other method, no framework limitation. Same
    destroy() override pattern as purchases.views
    .PurchaseOrderDetailView.destroy().
    """
    permission_classes = [IsAdminOrSuperuser]
    serializer_class    = RecipeReadSerializer

    def get_object(self):
        return get_recipe_by_id(self.kwargs["pk"])

    def destroy(self, request, *args, **kwargs):
        serializer = DeleteRecipeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        delete_recipe(
            recipe_id=self.kwargs["pk"],
            jumbo_shelf_allocations=d.get("jumbo_shelf_allocations"),
            cores_shelf_allocations=d.get("cores_shelf_allocations"),
            user=request.user,
        )
        return Response({"detail": "Recipe deleted."}, status=status.HTTP_200_OK)


class UpdateRecipeDescriptionView(APIView):
    """PATCH /production/recipes/<pk>/description/"""
    permission_classes = [IsAdminOrSuperuser]

    def patch(self, request, pk):
        serializer = UpdateRecipeDescriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        update_recipe_description(recipe_id=pk, description=serializer.validated_data["description"], user=request.user)
        return Response(RecipeReadSerializer(get_recipe_by_id(pk)).data, status=status.HTTP_200_OK)


class UpdateRecipeNameView(APIView):
    """PATCH /production/recipes/<pk>/name/"""
    permission_classes = [IsAdminOrSuperuser]

    def patch(self, request, pk):
        serializer = UpdateRecipeNameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        update_recipe_name(recipe_id=pk, name=serializer.validated_data["name"], user=request.user)
        return Response(RecipeReadSerializer(get_recipe_by_id(pk)).data, status=status.HTTP_200_OK)


class IssueMaterialView(APIView):
    """POST /production/recipes/<pk>/issue-material/"""
    permission_classes = [IsAdminOrSuperuser]

    def post(self, request, pk):
        serializer = IssueMaterialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        issue_material(
            recipe_id=pk, kind=d["kind"], product_id=d["product_id"], quantity=d["quantity"],
            shelf_allocations=d["shelf_allocations"], user=request.user,
        )
        return Response(RecipeReadSerializer(get_recipe_by_id(pk)).data, status=status.HTTP_201_CREATED)


class UpdateIssuedMaterialView(APIView):
    """PATCH /production/recipes/<pk>/issued-materials/<kind>/"""
    permission_classes = [IsAdminOrSuperuser]

    def patch(self, request, pk, kind):
        serializer = UpdateIssuedMaterialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        update_issued_material(
            recipe_id=pk, kind=kind, new_quantity=d["quantity"],
            shelf_allocations=d["shelf_allocations"], user=request.user,
        )
        return Response(RecipeReadSerializer(get_recipe_by_id(pk)).data, status=status.HTTP_200_OK)


class AddBreakdownItemView(APIView):
    """POST /production/recipes/<pk>/breakdown-items/"""
    permission_classes = [IsAdminOrSuperuser]

    def post(self, request, pk):
        serializer = AddBreakdownItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        add_breakdown_item(
            recipe_id=pk, yard_value=d["yard_value"], quantity=d["quantity"],
            shelf_allocations=d["shelf_allocations"], user=request.user,
        )
        return Response(RecipeReadSerializer(get_recipe_by_id(pk)).data, status=status.HTTP_201_CREATED)


class BreakdownItemDetailView(APIView):
    """PATCH/DELETE /production/recipes/<pk>/breakdown-items/<item_id>/ — reuses AddBreakdownItemSerializer for PATCH, identical shape."""
    permission_classes = [IsAdminOrSuperuser]

    def patch(self, request, pk, item_id):
        serializer = AddBreakdownItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        update_breakdown_item(
            recipe_id=pk, item_id=item_id, yard_value=d["yard_value"], quantity=d["quantity"],
            shelf_allocations=d["shelf_allocations"], user=request.user,
        )
        return Response(RecipeReadSerializer(get_recipe_by_id(pk)).data, status=status.HTTP_200_OK)

    def delete(self, request, pk, item_id):
        delete_breakdown_item(recipe_id=pk, item_id=item_id, user=request.user)
        return Response(RecipeReadSerializer(get_recipe_by_id(pk)).data, status=status.HTTP_200_OK)


class FinishRecipeView(APIView):
    """POST /production/recipes/<pk>/finish/"""
    permission_classes = [IsAdminOrSuperuser]

    def post(self, request, pk):
        finish_recipe(recipe_id=pk, user=request.user)
        return Response(RecipeReadSerializer(get_recipe_by_id(pk)).data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Recipe (Cutting) — parallel endpoint set to the Rewinding ones above,
# pointed at the Cutting service/selector functions and its own read
# serializer (see serializers.py for why it's separate from RecipeReadSerializer).
# ---------------------------------------------------------------------------

class CuttingRecipeListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminOrSuperuser]

    def get_serializer_class(self):
        return CreateCuttingRecipeSerializer if self.request.method == "POST" else CuttingRecipeReadSerializer

    def get_queryset(self):
        p = self.request.query_params
        return get_all_cutting_recipes(status=p.get("status"), search=p.get("search"))

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        recipe = create_cutting_recipe(name=d["name"], description=d.get("description", ""), user=request.user)
        return Response(CuttingRecipeReadSerializer(recipe).data, status=status.HTTP_201_CREATED)


class CuttingRecipeRetrieveView(generics.RetrieveDestroyAPIView):
    """See RecipeRetrieveView's docstring — same destroy()-reads-a-body pattern."""
    permission_classes = [IsAdminOrSuperuser]
    serializer_class    = CuttingRecipeReadSerializer

    def get_object(self):
        return get_cutting_recipe_by_id(self.kwargs["pk"])

    def destroy(self, request, *args, **kwargs):
        serializer = DeleteCuttingRecipeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        delete_cutting_recipe(
            recipe_id=self.kwargs["pk"],
            shelf_allocations=serializer.validated_data.get("shelf_allocations"),
            user=request.user,
        )
        return Response({"detail": "Recipe deleted."}, status=status.HTTP_200_OK)


class UpdateCuttingRecipeDescriptionView(APIView):
    """PATCH /production/cutting-recipes/<pk>/description/"""
    permission_classes = [IsAdminOrSuperuser]

    def patch(self, request, pk):
        serializer = UpdateRecipeDescriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        update_recipe_description(recipe_id=pk, description=serializer.validated_data["description"], user=request.user)
        return Response(CuttingRecipeReadSerializer(get_cutting_recipe_by_id(pk)).data, status=status.HTTP_200_OK)


class UpdateCuttingRecipeNameView(APIView):
    """PATCH /production/cutting-recipes/<pk>/name/"""
    permission_classes = [IsAdminOrSuperuser]

    def patch(self, request, pk):
        serializer = UpdateRecipeNameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        update_recipe_name(recipe_id=pk, name=serializer.validated_data["name"], user=request.user)
        return Response(CuttingRecipeReadSerializer(get_cutting_recipe_by_id(pk)).data, status=status.HTTP_200_OK)


class IssueCuttingMaterialView(APIView):
    """POST /production/cutting-recipes/<pk>/issue-material/"""
    permission_classes = [IsAdminOrSuperuser]

    def post(self, request, pk):
        serializer = IssueCuttingMaterialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        issue_cutting_material(
            recipe_id=pk, wip_product_id=d["wip_product_id"], quantity=d["quantity"],
            shelf_allocations=d["shelf_allocations"], user=request.user,
        )
        return Response(CuttingRecipeReadSerializer(get_cutting_recipe_by_id(pk)).data, status=status.HTTP_201_CREATED)


class UpdateCuttingIssuedMaterialView(APIView):
    """PATCH /production/cutting-recipes/<pk>/issued-material/"""
    permission_classes = [IsAdminOrSuperuser]

    def patch(self, request, pk):
        serializer = UpdateIssuedMaterialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        update_cutting_issued_material(
            recipe_id=pk, new_quantity=d["quantity"],
            shelf_allocations=d["shelf_allocations"], user=request.user,
        )
        return Response(CuttingRecipeReadSerializer(get_cutting_recipe_by_id(pk)).data, status=status.HTTP_200_OK)


class AddCuttingBreakdownItemView(APIView):
    """POST /production/cutting-recipes/<pk>/breakdown-items/"""
    permission_classes = [IsAdminOrSuperuser]

    def post(self, request, pk):
        serializer = AddCuttingBreakdownItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        add_cutting_breakdown_item(
            recipe_id=pk, length_mm=d["length_mm"], quantity=d["quantity"],
            shelf_allocations=d["shelf_allocations"], user=request.user,
        )
        return Response(CuttingRecipeReadSerializer(get_cutting_recipe_by_id(pk)).data, status=status.HTTP_201_CREATED)


class CuttingBreakdownItemDetailView(APIView):
    """PATCH/DELETE /production/cutting-recipes/<pk>/breakdown-items/<item_id>/ — reuses AddCuttingBreakdownItemSerializer for PATCH, identical shape."""
    permission_classes = [IsAdminOrSuperuser]

    def patch(self, request, pk, item_id):
        serializer = AddCuttingBreakdownItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        update_cutting_breakdown_item(
            recipe_id=pk, item_id=item_id, length_mm=d["length_mm"], quantity=d["quantity"],
            shelf_allocations=d["shelf_allocations"], user=request.user,
        )
        return Response(CuttingRecipeReadSerializer(get_cutting_recipe_by_id(pk)).data, status=status.HTTP_200_OK)

    def delete(self, request, pk, item_id):
        delete_cutting_breakdown_item(recipe_id=pk, item_id=item_id, user=request.user)
        return Response(CuttingRecipeReadSerializer(get_cutting_recipe_by_id(pk)).data, status=status.HTTP_200_OK)


class FinishCuttingRecipeView(APIView):
    """POST /production/cutting-recipes/<pk>/finish/"""
    permission_classes = [IsAdminOrSuperuser]

    def post(self, request, pk):
        finish_cutting_recipe(recipe_id=pk, user=request.user)
        return Response(CuttingRecipeReadSerializer(get_cutting_recipe_by_id(pk)).data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# FG Product / Inventory - read-only
# ---------------------------------------------------------------------------

class IssuableCuttingPieceListView(generics.ListAPIView):
    """GET /production/issuable-cutting-pieces/?search=... - Cut Pieces only, for Packing issuance."""
    permission_classes = [IsAdminOrSuperuser]
    serializer_class    = IssuableCuttingPieceSerializer

    def get_queryset(self):
        return get_issuable_cutting_pieces(search=self.request.query_params.get("search"))


class FgInventoryListView(generics.ListAPIView):
    permission_classes = [IsAdminOrSuperuser]
    serializer_class    = FgInventoryReadSerializer

    def get_queryset(self):
        return get_all_fg_inventory(search=self.request.query_params.get("search"))


class FgShelfStockListView(generics.ListAPIView):
    """GET /production/shelves/<pk>/fg-stock/ - FG products + quantities on one shelf."""
    permission_classes = [IsAdminOrSuperuser]
    serializer_class    = FgShelfStockReadSerializer

    def get_queryset(self):
        from purchases.selectors import get_shelf_by_id
        get_shelf_by_id(self.kwargs["pk"])  # 404s if the shelf doesn't exist
        return get_fg_shelf_stock_rows(self.kwargs["pk"], search=self.request.query_params.get("search"))


class CandidateShelvesForFgProductListView(generics.ListAPIView):
    """GET /production/fg-shelves/candidates/?fg_product_id=<id>&search=... - mirrors CandidateShelvesForWipProductListView."""
    permission_classes = [IsAdminOrSuperuser]
    serializer_class    = CandidateShelfSerializer

    def get_queryset(self):
        from rest_framework.exceptions import ValidationError
        fg_product_id = self.request.query_params.get("fg_product_id")
        if not fg_product_id:
            raise ValidationError({"fg_product_id": "This query parameter is required."})
        return get_candidate_shelves_for_fg_product(
            int(fg_product_id), search=self.request.query_params.get("search"),
        )


# ---------------------------------------------------------------------------
# Recipe (Packing) - parallel endpoint set to Rewinding/Cutting's, pointed at
# the Packing service/selector functions and its own read serializer.
# ---------------------------------------------------------------------------

class PackingRecipeListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminOrSuperuser]

    def get_serializer_class(self):
        return CreatePackingRecipeSerializer if self.request.method == "POST" else PackingRecipeReadSerializer

    def get_queryset(self):
        p = self.request.query_params
        return get_all_packing_recipes(status=p.get("status"), search=p.get("search"))

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        recipe = create_packing_recipe(name=d["name"], description=d.get("description", ""), user=request.user)
        return Response(PackingRecipeReadSerializer(recipe).data, status=status.HTTP_201_CREATED)


class PackingRecipeRetrieveView(generics.RetrieveDestroyAPIView):
    """See RecipeRetrieveView's docstring — same destroy()-reads-a-body pattern."""
    permission_classes = [IsAdminOrSuperuser]
    serializer_class    = PackingRecipeReadSerializer

    def get_object(self):
        return get_packing_recipe_by_id(self.kwargs["pk"])

    def destroy(self, request, *args, **kwargs):
        serializer = DeletePackingRecipeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        delete_packing_recipe(
            recipe_id=self.kwargs["pk"],
            piece_shelf_allocations=d.get("piece_shelf_allocations"),
            material_shelf_allocations=d.get("material_shelf_allocations"),
            user=request.user,
        )
        return Response({"detail": "Recipe deleted."}, status=status.HTTP_200_OK)


class UpdatePackingRecipeDescriptionView(APIView):
    """PATCH /production/packing-recipes/<pk>/description/"""
    permission_classes = [IsAdminOrSuperuser]

    def patch(self, request, pk):
        serializer = UpdateRecipeDescriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        update_recipe_description(recipe_id=pk, description=serializer.validated_data["description"], user=request.user)
        return Response(PackingRecipeReadSerializer(get_packing_recipe_by_id(pk)).data, status=status.HTTP_200_OK)


class UpdatePackingRecipeNameView(APIView):
    """PATCH /production/packing-recipes/<pk>/name/"""
    permission_classes = [IsAdminOrSuperuser]

    def patch(self, request, pk):
        serializer = UpdateRecipeNameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        update_recipe_name(recipe_id=pk, name=serializer.validated_data["name"], user=request.user)
        return Response(PackingRecipeReadSerializer(get_packing_recipe_by_id(pk)).data, status=status.HTTP_200_OK)


class IssuePackingPieceView(APIView):
    """POST /production/packing-recipes/<pk>/issue-piece/"""
    permission_classes = [IsAdminOrSuperuser]

    def post(self, request, pk):
        serializer = IssuePackingPieceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        issue_packing_piece(
            recipe_id=pk, wip_product_id=d["wip_product_id"], quantity=d["quantity"],
            shelf_allocations=d["shelf_allocations"], user=request.user,
        )
        return Response(PackingRecipeReadSerializer(get_packing_recipe_by_id(pk)).data, status=status.HTTP_201_CREATED)


class UpdatePackingIssuedPieceView(APIView):
    """PATCH /production/packing-recipes/<pk>/issued-piece/"""
    permission_classes = [IsAdminOrSuperuser]

    def patch(self, request, pk):
        serializer = UpdateIssuedMaterialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        update_packing_issued_piece(
            recipe_id=pk, new_quantity=d["quantity"],
            shelf_allocations=d["shelf_allocations"], user=request.user,
        )
        return Response(PackingRecipeReadSerializer(get_packing_recipe_by_id(pk)).data, status=status.HTTP_200_OK)


class IssuePackingMaterialView(APIView):
    """POST /production/packing-recipes/<pk>/issue-material/"""
    permission_classes = [IsAdminOrSuperuser]

    def post(self, request, pk):
        serializer = IssuePackingMaterialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        issue_packing_material(
            recipe_id=pk, product_id=d["product_id"], quantity=d["quantity"],
            shelf_allocations=d["shelf_allocations"], user=request.user,
        )
        return Response(PackingRecipeReadSerializer(get_packing_recipe_by_id(pk)).data, status=status.HTTP_201_CREATED)


class UpdatePackingIssuedMaterialView(APIView):
    """PATCH /production/packing-recipes/<pk>/issued-material/"""
    permission_classes = [IsAdminOrSuperuser]

    def patch(self, request, pk):
        serializer = UpdateIssuedMaterialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        update_packing_issued_material(
            recipe_id=pk, new_quantity=d["quantity"],
            shelf_allocations=d["shelf_allocations"], user=request.user,
        )
        return Response(PackingRecipeReadSerializer(get_packing_recipe_by_id(pk)).data, status=status.HTTP_200_OK)


class FinishPackingRecipeView(APIView):
    """POST /production/packing-recipes/<pk>/finish/"""
    permission_classes = [IsAdminOrSuperuser]

    def post(self, request, pk):
        serializer = FinishPackingRecipeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        finish_packing_recipe(
            recipe_id=pk, shelf_allocations=serializer.validated_data["shelf_allocations"], user=request.user,
        )
        return Response(PackingRecipeReadSerializer(get_packing_recipe_by_id(pk)).data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Recipe Labor / Machine / Time — shared across all 3 recipe types (Recipe
# is one shared model/table). Registered under all three URL prefixes
# (recipes/, cutting-recipes/, packing-recipes/) pointing at these same
# views; each response is shaped by the recipe's own actual recipe_type,
# not by which prefix was used to reach it.
# ---------------------------------------------------------------------------

_RECIPE_DETAIL_BY_TYPE = {
    Recipe.RecipeType.REWINDING: (get_recipe_by_id, RecipeReadSerializer),
    Recipe.RecipeType.CUTTING:   (get_cutting_recipe_by_id, CuttingRecipeReadSerializer),
    Recipe.RecipeType.PACKING:   (get_packing_recipe_by_id, PackingRecipeReadSerializer),
}


def _recipe_detail_response(pk):
    recipe_type = Recipe.objects.only("recipe_type").get(pk=pk).recipe_type
    getter, serializer_cls = _RECIPE_DETAIL_BY_TYPE[recipe_type]
    return Response(serializer_cls(getter(pk)).data, status=status.HTTP_200_OK)


class SetRecipeTimeView(APIView):
    """PATCH /production/<recipes|cutting-recipes|packing-recipes>/<pk>/time/"""
    permission_classes = [IsAdminOrSuperuser]

    def patch(self, request, pk):
        serializer = SetRecipeTimeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        set_recipe_time(recipe_id=pk, hours=d["time_hours"], minutes=d["time_minutes"], user=request.user)
        return _recipe_detail_response(pk)


class RecipeLaborListCreateView(APIView):
    """POST /production/<...>/<pk>/labor/ — add an employee to the recipe."""
    permission_classes = [IsAdminOrSuperuser]

    def post(self, request, pk):
        serializer = AddRecipeLaborSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        add_recipe_labor(recipe_id=pk, employee_id=serializer.validated_data["employee_id"], user=request.user)
        return _recipe_detail_response(pk)


class RecipeLaborDeleteView(APIView):
    """DELETE /production/<...>/<pk>/labor/<employee_id>/"""
    permission_classes = [IsAdminOrSuperuser]

    def delete(self, request, pk, employee_id):
        remove_recipe_labor(recipe_id=pk, employee_id=employee_id, user=request.user)
        return _recipe_detail_response(pk)


class RecipeMachineListCreateView(APIView):
    """POST /production/<...>/<pk>/machines/ — add a machine to the recipe."""
    permission_classes = [IsAdminOrSuperuser]

    def post(self, request, pk):
        serializer = AddRecipeMachineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        add_recipe_machine(recipe_id=pk, machine_id=serializer.validated_data["machine_id"], user=request.user)
        return _recipe_detail_response(pk)


class RecipeMachineDeleteView(APIView):
    """DELETE /production/<...>/<pk>/machines/<machine_id>/"""
    permission_classes = [IsAdminOrSuperuser]

    def delete(self, request, pk, machine_id):
        remove_recipe_machine(recipe_id=pk, machine_id=machine_id, user=request.user)
        return _recipe_detail_response(pk)
