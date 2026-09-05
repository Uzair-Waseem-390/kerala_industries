# Split by stage so this package doesn't grow into one giant file the way
# purchases/billing did — rewinding.py today, cutting.py once that stage is
# built. Re-exports here are the only reason `from production.selectors
# import X` still works unchanged after the split — keep this list in sync
# with rewinding.py's public functions.
from .rewinding import (
    get_all_recipes, get_all_rewound_core_bindings, get_all_rewound_core_length_mms,
    get_all_rewound_core_yards, get_all_wip_products,
    get_issuable_products, get_issued_material, get_recipe_by_id,
    get_rewound_core_binding_by_id, get_rewound_core_length_mm_by_id,
    get_rewound_core_yard_by_id, get_wip_product_by_id,
)
from .cutting import (
    get_all_cutting_recipes, get_available_wip_batches_for_fifo, get_cutting_issued_material,
    get_cutting_recipe_by_id, get_issuable_wip_cores,
)
# WIP inventory-tracking selectors now live in the inventory app (2026-09) —
# re-exported here so `from production.selectors import X` still works
# unchanged for production/views.py.
from inventory.selectors import (
    get_all_wip_inventory, get_candidate_shelves_for_wip_product, get_wip_shelf_stock_rows,
)

__all__ = [
    "get_all_recipes", "get_all_rewound_core_bindings", "get_all_rewound_core_length_mms",
    "get_all_rewound_core_yards", "get_all_wip_inventory", "get_all_wip_products",
    "get_issuable_products", "get_issued_material", "get_recipe_by_id",
    "get_rewound_core_binding_by_id", "get_rewound_core_length_mm_by_id",
    "get_rewound_core_yard_by_id", "get_wip_product_by_id", "get_wip_shelf_stock_rows",
    "get_all_cutting_recipes", "get_available_wip_batches_for_fifo", "get_cutting_issued_material",
    "get_cutting_recipe_by_id", "get_issuable_wip_cores", "get_candidate_shelves_for_wip_product",
]
