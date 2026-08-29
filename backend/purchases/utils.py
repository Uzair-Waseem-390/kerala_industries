from decimal import ROUND_HALF_UP, Decimal


def calculate_total_price(
    quantity: int,
    unit_price: Decimal,
    gst: Decimal,
    wht: Decimal,
) -> dict:
    """
    Single source of truth for the ERP purchase price calculation.

    Formula (Pakistan FBR standard):
        gross_amount = quantity × unit_price
        gst_amount   = gross_amount × (gst  / 100)   — added to payable
        wht_amount   = gross_amount × (wht  / 100)   — deducted from payable (WHT on gross)
        total_price  = gross_amount + gst_amount - wht_amount

    Example:
        qty=10, unit_price=100.5, gst=18.5%, wht=1.5%
        gross  = 1005.0000
        gst    =  185.9250
        wht    =   15.0750
        total  = 1175.8500

    Returns a dict of all four computed Decimal values so callers can store
    each breakdown field individually without re-computing.
    """
    qty = Decimal(str(quantity))
    up = Decimal(str(unit_price))
    gst_pct = Decimal(str(gst))
    wht_pct = Decimal(str(wht))

    gross_amount = qty * up
    gst_amount = gross_amount * (gst_pct / Decimal("100"))
    wht_amount = gross_amount * (wht_pct / Decimal("100"))
    total_price = gross_amount + gst_amount - wht_amount

    precision = Decimal("0.0001")
    return {
        "gross_amount": gross_amount.quantize(precision, rounding=ROUND_HALF_UP),
        "gst_amount": gst_amount.quantize(precision, rounding=ROUND_HALF_UP),
        "wht_amount": wht_amount.quantize(precision, rounding=ROUND_HALF_UP),
        "total_price": total_price.quantize(precision, rounding=ROUND_HALF_UP),
    }


# Client-specified conversion factor (not the more precise 1/0.9144 —
# using the exact multiplier the client gave us): "5 meters: 5 × 1.09361 =
# 5.46805 yards".
METERS_TO_YARDS_FACTOR = Decimal("1.09361")


def meters_to_yards(meters: Decimal) -> Decimal:
    """Converts a meter length to yards using the client's specified factor."""
    m = Decimal(str(meters))
    yards = m * METERS_TO_YARDS_FACTOR
    return yards.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Product variant key
# ---------------------------------------------------------------------------
# Ordered list of the attribute-FK fields Product can carry — fixed order so
# the computed key is deterministic regardless of call-site kwarg order.
VARIANT_ATTRIBUTE_FIELDS = [
    "jumbo_name", "core_name", "core_length",
    "core_thickness", "packing_size", "carton_size",
]


def compute_anchor_variant_key(*, code: str) -> str:
    """
    variant_key for one of the 4 canonical family-anchor Product rows
    (Jumbo/Cores/Packing/Cartons — created only by create_product(), never
    by get_or_create_product_variant()). Derived from `code`, which is
    already unique=True on its own — this just gives every Product row a
    variant_key, anchor or variant, so the single unique constraint covers
    both without a nullable-column special case.
    """
    return f"anchor:{code}"


def compute_variant_key(*, base_product_id: int, **attribute_ids) -> str:
    """
    Deterministic fingerprint of (base_product + every attribute FK on
    Product), used as Product.variant_key for attribute-bearing variants —
    a real, DB-enforced uniqueness guarantee that a plain unique_together
    across nullable FK columns can't provide (NULL is never equal to NULL
    in a uniqueness check, so two rows sharing one populated attribute but
    NULL on the rest wouldn't collide under a plain composite constraint).
    Unset attributes pass as None/omitted — both render as the same empty
    segment, so omitting a kwarg and passing it as None are equivalent.

    base_product identifies WHICH anchor line this is a variant of (Jumbo
    vs Cores vs Packing vs Cartons) — Family alone can't disambiguate that,
    since every anchor shares family="Raw Material".

    Callers pass whichever of VARIANT_ATTRIBUTE_FIELDS apply, e.g.:
        compute_variant_key(base_product_id=1, jumbo_name_id=3)
    """
    parts = [f"base={base_product_id}"]
    for field in VARIANT_ATTRIBUTE_FIELDS:
        value = attribute_ids.get(f"{field}_id")
        parts.append(f"{field}={value if value is not None else ''}")
    return "|".join(parts)