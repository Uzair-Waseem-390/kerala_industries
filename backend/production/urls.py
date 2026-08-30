from django.urls import path

from .views import (
    AddBreakdownItemView,
    FinishRecipeView,
    IssuableProductListView,
    IssueMaterialView,
    RecipeListCreateView,
    RecipeRetrieveView,
    RewoundCoreBindingListView,
    RewoundCoreBindingRetrieveView,
    RewoundCoreLengthMmListView,
    RewoundCoreLengthMmRetrieveView,
    RewoundCoreYardListView,
    RewoundCoreYardRetrieveView,
    UpdateIssuedMaterialView,
    WipInventoryListView,
    WipProductListView,
    WipProductRetrieveView,
)

urlpatterns = [
    # WIP attribute lookups (Rewinding) — read-only
    path("rewound-core-bindings/",             RewoundCoreBindingListView.as_view(),     name="rewound-core-binding-list"),
    path("rewound-core-bindings/<int:pk>/",    RewoundCoreBindingRetrieveView.as_view(), name="rewound-core-binding-detail"),
    path("rewound-core-yards/",                RewoundCoreYardListView.as_view(),        name="rewound-core-yard-list"),
    path("rewound-core-yards/<int:pk>/",       RewoundCoreYardRetrieveView.as_view(),    name="rewound-core-yard-detail"),
    path("rewound-core-length-mms/",           RewoundCoreLengthMmListView.as_view(),    name="rewound-core-length-mm-list"),
    path("rewound-core-length-mms/<int:pk>/",  RewoundCoreLengthMmRetrieveView.as_view(), name="rewound-core-length-mm-detail"),

    # WIP Product / Inventory — read-only
    path("wip-products/",           WipProductListView.as_view(),     name="wip-product-list"),
    path("wip-products/<int:pk>/",  WipProductRetrieveView.as_view(), name="wip-product-detail"),
    path("wip-inventory/",          WipInventoryListView.as_view(),   name="wip-inventory-list"),

    # RM products issuable into a recipe
    path("issuable-products/", IssuableProductListView.as_view(), name="issuable-product-list"),

    # Recipes
    path("recipes/",     RecipeListCreateView.as_view(), name="recipe-list-create"),
    path("recipes/<int:pk>/", RecipeRetrieveView.as_view(), name="recipe-detail"),
    path("recipes/<int:pk>/issue-material/",   IssueMaterialView.as_view(),      name="recipe-issue-material"),
    path("recipes/<int:pk>/issued-materials/<str:kind>/", UpdateIssuedMaterialView.as_view(), name="recipe-update-issued-material"),
    path("recipes/<int:pk>/breakdown-items/",  AddBreakdownItemView.as_view(),   name="recipe-add-breakdown-item"),
    path("recipes/<int:pk>/finish/",           FinishRecipeView.as_view(),      name="recipe-finish"),
]
