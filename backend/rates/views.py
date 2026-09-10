from rest_framework import generics, serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .permissions import IsAdminOrSuperuserOrReadOnly
from .selectors import (
    get_all_rates,
    get_history_for_product,
    get_rate_by_id,
    get_unpriced_products,
)
from .serializers import (
    ProductRateCreateSerializer,
    ProductRateHistorySerializer,
    ProductRateReadSerializer,
    ProductRateUpdateSerializer,
)
from .services import create_rate, update_rate


# ---------------------------------------------------------------------------
# Rate list: GET (all users) + POST (admin/superuser)
# ---------------------------------------------------------------------------

class ProductRateListCreateView(generics.ListCreateAPIView):
    """
    GET  /rates/              — list all current rates with filters + search
    POST /rates/              — set a rate for a new product (FG, or an RM
                                 Cartons-family variant — see create_rate)

    Query params for GET:
        search      : product name or code (partial, case-insensitive)
        min_price   : minimum selling price
        max_price   : maximum selling price
    """

    permission_classes = [IsAdminOrSuperuserOrReadOnly]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ProductRateCreateSerializer
        return ProductRateReadSerializer

    def get_queryset(self):
        params = self.request.query_params
        return get_all_rates(
            search=params.get("search"),
            min_price=params.get("min_price"),
            max_price=params.get("max_price"),
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        rate = create_rate(
            rm_product_id=d.get("rm_product_id"),
            fg_product_id=d.get("fg_product_id"),
            selling_price=d["selling_price"],
            user=request.user,
            note=d.get("note", ""),
        )
        return Response(ProductRateReadSerializer(rate).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Single rate: GET + PATCH (product field is immutable after creation)
# ---------------------------------------------------------------------------

class ProductRateRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    """
    GET   /rates/<pk>/        — retrieve a single rate
    PATCH /rates/<pk>/        — update selling price (admin/superuser only)

    Product is intentionally immutable after creation.
    To change the product, delete this rate and create a new one.
    """

    permission_classes = [IsAdminOrSuperuserOrReadOnly]
    http_method_names = ["get", "patch"]

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return ProductRateUpdateSerializer
        return ProductRateReadSerializer

    def get_object(self):
        return get_rate_by_id(self.kwargs["pk"])

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        rate = update_rate(
            pk=self.kwargs["pk"],
            selling_price=d["selling_price"],
            user=request.user,
            note=d.get("note", ""),
        )
        return Response(ProductRateReadSerializer(rate).data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Unpriced products — products with no rate set yet, browsed/searched
# independently of the (already paginated) rates list above. Returned as
# plain dicts (see get_unpriced_products) since FG + RM Cartons variants
# come from two different model tables with no shared base.
# ---------------------------------------------------------------------------

class UnpricedProductItemSerializer(serializers.Serializer):
    id      = serializers.IntegerField()
    type    = serializers.CharField()
    name    = serializers.CharField()
    code    = serializers.CharField()
    product = serializers.SerializerMethodField()

    def get_product(self, obj):
        if obj["type"] == "fg":
            from production.serializers import FgProductReadSerializer
            return FgProductReadSerializer(obj["product"]).data
        from purchases.serializers import ProductReadSerializer
        return ProductReadSerializer(obj["product"]).data


class UnpricedProductListView(generics.ListAPIView):
    """
    GET /rates/unpriced/       — products with no ProductRate yet

    Query params:
        search   : product name or code (partial, case-insensitive)
    """

    permission_classes = [IsAdminOrSuperuserOrReadOnly]
    serializer_class = UnpricedProductItemSerializer

    def get_queryset(self):
        p = self.request.query_params
        return get_unpriced_products(search=p.get("search"))


# ---------------------------------------------------------------------------
# Rate history for a specific product
# ---------------------------------------------------------------------------

class ProductRateHistoryView(generics.ListAPIView):
    """
    GET /rates/history/<product_type>/<product_id>/
    product_type is "rm" or "fg". Returns full price change history for a
    product, newest first. Accessible to all authenticated users — useful
    for transparency.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = ProductRateHistorySerializer

    def get_queryset(self):
        product_type = self.kwargs["product_type"]
        product_id = self.kwargs["product_id"]
        if product_type == "fg":
            return get_history_for_product(fg_product_id=product_id)
        return get_history_for_product(rm_product_id=product_id)
