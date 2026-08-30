from decimal import ROUND_HALF_UP, Decimal

# Rewinding stage: RM core length is entered in inches, the derived WIP
# product name/attribute needs it in mm.
INCHES_TO_MM_FACTOR = Decimal("25.4")


def inches_to_mm(inches: Decimal) -> Decimal:
    value = Decimal(str(inches))
    mm = value * INCHES_TO_MM_FACTOR
    return mm.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def compute_wip_variant_key(*, binding_id: int, yard_id: int, length_mm_id: int) -> str:
    """
    Deterministic fingerprint for a WipProduct — same role as
    purchases.utils.compute_variant_key. Two breakdown items resolving to
    the same (binding, yard, length_mm) combo hit the same WipProduct row.
    """
    return f"binding={binding_id}|yard={yard_id}|length_mm={length_mm_id}"
