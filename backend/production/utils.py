from decimal import ROUND_HALF_UP, Decimal

# Rewinding stage: RM core length is entered in inches, the derived WIP
# product name/attribute needs it in mm.
INCHES_TO_MM_FACTOR = Decimal("25.4")


def inches_to_mm(inches: Decimal) -> Decimal:
    value = Decimal(str(inches))
    mm = value * INCHES_TO_MM_FACTOR
    return mm.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def compute_wip_variant_key(*, binding_id: int, yard_id: int, length_mm_id: int, stage: str) -> str:
    """
    Deterministic fingerprint for a WipProduct — same role as
    purchases.utils.compute_variant_key. Two breakdown items resolving to
    the same (binding, yard, length_mm, stage) combo hit the same WipProduct
    row. `stage` is part of the key (not just an attribute) so a whole
    Rewound Core and a Cut Piece can never collide into the same row even if
    their numeric attributes coincidentally match — they're physically
    different things.
    """
    return f"binding={binding_id}|yard={yard_id}|length_mm={length_mm_id}|stage={stage}"


# select_related path list for WipProduct — used wherever a queryset feeds
# WipProductReadSerializer (directly, or nested under a breakdown item),
# by both production's own selectors and inventory.selectors (which needs
# it for WIP inventory listings but must not import through
# production.selectors, to avoid a circular import with that package's
# __init__.py re-exports — hence this lives in the leaf utils module, not
# selectors/_shared.py).
#
# WipProductReadSerializer nests RewoundCoreBindingReadSerializer/
# YardReadSerializer/LengthMmReadSerializer, each of which extends
# AuditReadMixin (created_by/updated_by StringRelatedFields) — found via a
# query-count check while verifying Cutting (2026-09): selecting only
# "binding"/"yard"/"length_mm" themselves covers the object, but not THEIR
# own created_by/updated_by, so every WipProduct row serialized fired up to
# 6 extra queries (one per nested attribute's created_by/updated_by).
WIP_PRODUCT_SELECT_RELATED = (
    "family",
    "binding", "binding__created_by", "binding__updated_by",
    "yard", "yard__created_by", "yard__updated_by",
    "length_mm", "length_mm__created_by", "length_mm__updated_by",
    "created_by", "updated_by",
)
