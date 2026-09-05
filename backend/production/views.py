from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsAdminOrSuperuser
from .selectors import (
    get_all_cutting_recipes, get_all_recipes, get_all_rewound_core_bindings,
    get_all_rewound_core_length_mms, get_all_rewound_core_yards, get_all_wip_inventory,
    get_all_wip_products, get_candidate_shelves_for_wip_product, get_cutting_recipe_by_id,
    get_issuable_products, get_issuable_wip_cores, get_recipe_by_id, get_rewound_core_binding_by_id,
    get_rewound_core_length_mm_by_id, get_rewound_core_yard_by_id, get_wip_product_by_id,
    get_wip_shelf_stock_rows,
)
from .serializers import (
    AddBreakdownItemSerializer, AddCuttingBreakdownItemSerializer, CandidateShelfSerializer,
    CreateCuttingRecipeSerializer, CuttingRecipeReadSerializer, IssuableProductSerializer,
    IssuableWipCoreSerializer, IssueCuttingMaterialSerializer, IssueMaterialSerializer,
    RecipeCreateSerializer, RecipeReadSerializer, RewoundCoreBindingReadSerializer,
    RewoundCoreLengthMmReadSerializer, RewoundCoreYardReadSerializer, UpdateIssuedMaterialSerializer,
    UpdateRecipeDescriptionSerializer, WipInventoryReadSerializer, WipProductReadSerializer,
    WipShelfStockReadSerializer,
)
from .services import (
    add_breakdown_item, add_cutting_breakdown_item, create_cutting_recipe, create_recipe,
    finish_cutting_recipe, finish_recipe, issue_cutting_material, issue_material,
    update_cutting_issued_material, update_issued_material, update_recipe_description,
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
        if kind not in ("jumbo", "cores"):
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"kind": "kind must be 'jumbo' or 'cores'."})
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


class RecipeRetrieveView(generics.RetrieveAPIView):
    permission_classes = [IsAdminOrSuperuser]
    serializer_class    = RecipeReadSerializer

    def get_object(self):
        return get_recipe_by_id(self.kwargs["pk"])


class UpdateRecipeDescriptionView(APIView):
    """PATCH /production/recipes/<pk>/description/"""
    permission_classes = [IsAdminOrSuperuser]

    def patch(self, request, pk):
        serializer = UpdateRecipeDescriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        update_recipe_description(recipe_id=pk, description=serializer.validated_data["description"], user=request.user)
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


class CuttingRecipeRetrieveView(generics.RetrieveAPIView):
    permission_classes = [IsAdminOrSuperuser]
    serializer_class    = CuttingRecipeReadSerializer

    def get_object(self):
        return get_cutting_recipe_by_id(self.kwargs["pk"])


class UpdateCuttingRecipeDescriptionView(APIView):
    """PATCH /production/cutting-recipes/<pk>/description/"""
    permission_classes = [IsAdminOrSuperuser]

    def patch(self, request, pk):
        serializer = UpdateRecipeDescriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        update_recipe_description(recipe_id=pk, description=serializer.validated_data["description"], user=request.user)
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


class FinishCuttingRecipeView(APIView):
    """POST /production/cutting-recipes/<pk>/finish/"""
    permission_classes = [IsAdminOrSuperuser]

    def post(self, request, pk):
        finish_cutting_recipe(recipe_id=pk, user=request.user)
        return Response(CuttingRecipeReadSerializer(get_cutting_recipe_by_id(pk)).data, status=status.HTTP_200_OK)
