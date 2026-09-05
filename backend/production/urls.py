from django.urls import path

from .views import (
    AddBreakdownItemView,
    AddCuttingBreakdownItemView,
    CandidateShelvesForWipProductListView,
    CuttingRecipeListCreateView,
    CuttingRecipeRetrieveView,
    FinishCuttingRecipeView,
    FinishRecipeView,
    IssuableProductListView,
    IssuableWipCoreListView,
    IssueCuttingMaterialView,
    IssueMaterialView,
    RecipeListCreateView,
    RecipeRetrieveView,
    RewoundCoreBindingListView,
    RewoundCoreBindingRetrieveView,
    RewoundCoreLengthMmListView,
    RewoundCoreLengthMmRetrieveView,
    RewoundCoreYardListView,
    RewoundCoreYardRetrieveView,
    UpdateCuttingIssuedMaterialView,
    UpdateCuttingRecipeDescriptionView,
    UpdateIssuedMaterialView,
    UpdateRecipeDescriptionView,
    WipInventoryListView,
    WipProductListView,
    WipProductRetrieveView,
    WipShelfStockListView,
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

    # WIP shelf stock — Shelf detail page's WIP tab
    path("shelves/<int:pk>/wip-stock/", WipShelfStockListView.as_view(), name="shelf-wip-stock-list"),

    # RM products issuable into a recipe
    path("issuable-products/", IssuableProductListView.as_view(), name="issuable-product-list"),

    # WIP cores issuable into a Cutting recipe
    path("issuable-wip-cores/", IssuableWipCoreListView.as_view(), name="issuable-wip-core-list"),

    # Shelves currently holding a given WIP product (consumption-side picker)
    path("wip-shelves/candidates/", CandidateShelvesForWipProductListView.as_view(), name="wip-shelf-candidates"),

    # Recipes (Rewinding)
    path("recipes/",     RecipeListCreateView.as_view(), name="recipe-list-create"),
    path("recipes/<int:pk>/", RecipeRetrieveView.as_view(), name="recipe-detail"),
    path("recipes/<int:pk>/description/",      UpdateRecipeDescriptionView.as_view(), name="recipe-update-description"),
    path("recipes/<int:pk>/issue-material/",   IssueMaterialView.as_view(),      name="recipe-issue-material"),
    path("recipes/<int:pk>/issued-materials/<str:kind>/", UpdateIssuedMaterialView.as_view(), name="recipe-update-issued-material"),
    path("recipes/<int:pk>/breakdown-items/",  AddBreakdownItemView.as_view(),   name="recipe-add-breakdown-item"),
    path("recipes/<int:pk>/finish/",           FinishRecipeView.as_view(),      name="recipe-finish"),

    # Recipes (Cutting)
    path("cutting-recipes/",     CuttingRecipeListCreateView.as_view(), name="cutting-recipe-list-create"),
    path("cutting-recipes/<int:pk>/", CuttingRecipeRetrieveView.as_view(), name="cutting-recipe-detail"),
    path("cutting-recipes/<int:pk>/description/",     UpdateCuttingRecipeDescriptionView.as_view(), name="cutting-recipe-update-description"),
    path("cutting-recipes/<int:pk>/issue-material/",  IssueCuttingMaterialView.as_view(),           name="cutting-recipe-issue-material"),
    path("cutting-recipes/<int:pk>/issued-material/", UpdateCuttingIssuedMaterialView.as_view(),    name="cutting-recipe-update-issued-material"),
    path("cutting-recipes/<int:pk>/breakdown-items/", AddCuttingBreakdownItemView.as_view(),        name="cutting-recipe-add-breakdown-item"),
    path("cutting-recipes/<int:pk>/finish/",           FinishCuttingRecipeView.as_view(),           name="cutting-recipe-finish"),
]
