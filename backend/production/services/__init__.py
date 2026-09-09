# Split by stage so this package doesn't grow into one giant file the way
# purchases/billing did — rewinding.py today, cutting.py once that stage is
# built (see instructions/multi-inventory-expansion.md-adjacent discussion,
# 2026-09). Re-exports here are the only reason `from production.services
# import X` still works unchanged after the split — keep this list in sync
# with rewinding.py's public functions.
from .rewinding import (
    add_breakdown_item, create_recipe, finish_recipe, issue_material,
    update_issued_material, update_recipe_description,
)
from .cutting import (
    add_cutting_breakdown_item, create_cutting_recipe, finish_cutting_recipe,
    issue_cutting_material, update_cutting_issued_material,
)
from .packing import (
    create_packing_recipe, finish_packing_recipe, issue_packing_material, issue_packing_piece,
    update_packing_issued_material, update_packing_issued_piece,
)
from ._shared import (
    add_recipe_labor, add_recipe_machine, remove_recipe_labor, remove_recipe_machine, set_recipe_time,
)

__all__ = [
    "add_breakdown_item", "create_recipe", "finish_recipe", "issue_material",
    "update_issued_material", "update_recipe_description",
    "add_cutting_breakdown_item", "create_cutting_recipe", "finish_cutting_recipe",
    "issue_cutting_material", "update_cutting_issued_material",
    "create_packing_recipe", "finish_packing_recipe", "issue_packing_material",
    "issue_packing_piece", "update_packing_issued_material", "update_packing_issued_piece",
    "add_recipe_labor", "add_recipe_machine", "remove_recipe_labor", "remove_recipe_machine", "set_recipe_time",
]
