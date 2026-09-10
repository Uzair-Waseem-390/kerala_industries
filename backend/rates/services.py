from decimal import Decimal

from django.db import IntegrityError, transaction

from purchases.selectors import get_product_by_id, is_cartons_product

from .models import ProductRate, ProductRateHistory, UnpricedProduct
from .selectors import get_rate_by_id, get_rate_by_product_id


def _is_fg(product) -> bool:
    from production.models import FgProduct
    return isinstance(product, FgProduct)


# ---------------------------------------------------------------------------
# Internal helper — always called after any price change
# ---------------------------------------------------------------------------

def _log_rate_history(*, product, selling_price: Decimal, user, note: str = "") -> None:
    """
    Append a new row to ProductRateHistory.
    Private — only called from within this service module.
    This is the single place responsible for keeping the audit log intact.
    """
    filter_kwargs = {"fg_product": product} if _is_fg(product) else {"rm_product": product}
    ProductRateHistory.objects.create(
        selling_price=selling_price,
        changed_by=user,
        note=note,
        **filter_kwargs,
    )


# ---------------------------------------------------------------------------
# Unpriced-products queue — kept in sync explicitly by whoever changes
# pricing status (see rates.models.UnpricedProduct for the full picture).
# purchases.services.create_product() calls add_to_unpriced_queue(product)
# via a lazy import exactly as before (RM side unchanged) — this function
# just now also accepts an FgProduct instance, for
# production.services.finish_packing_recipe's new call site.
# ---------------------------------------------------------------------------

def add_to_unpriced_queue(product) -> None:
    filter_kwargs = {"fg_product": product} if _is_fg(product) else {"rm_product": product}
    UnpricedProduct.objects.get_or_create(**filter_kwargs)


def remove_from_unpriced_queue(product) -> None:
    filter_kwargs = {"fg_product": product} if _is_fg(product) else {"rm_product": product}
    UnpricedProduct.objects.filter(**filter_kwargs).delete()


# ---------------------------------------------------------------------------
# Public services
# ---------------------------------------------------------------------------

@transaction.atomic
def create_rate(*, rm_product_id: int = None, fg_product_id: int = None, selling_price: Decimal, user, note: str = "") -> ProductRate:
    """
    Create a new ProductRate for a product — either an FG product, or an RM
    product that's a Cartons-family variant (the only RM line this app
    still prices). Raises ValidationError if a rate already exists for this
    product (use update_rate instead), or if an RM product outside the
    Cartons family is given.

    Atomic: the rate row and its first history entry are all-or-nothing —
    billing snapshots prices FROM the history table, so a rate must never
    exist without its matching history row.
    """
    from rest_framework.exceptions import ValidationError

    if bool(rm_product_id) == bool(fg_product_id):
        raise ValidationError({"product": "Exactly one of rm_product_id or fg_product_id is required."})

    if fg_product_id:
        from production.selectors import get_fg_product_by_id
        product = get_fg_product_by_id(fg_product_id)
        filter_kwargs = {"fg_product": product}
    else:
        product = get_product_by_id(rm_product_id)
        if not is_cartons_product(product):
            raise ValidationError({
                "rm_product_id": f"'{product.name}' can't be priced here — only Cartons and Finished Goods products are sellable.",
            })
        filter_kwargs = {"rm_product": product}

    duplicate_error = ValidationError(
        {"product": f"A rate already exists for '{product.name}'. Use PATCH to update it."}
    )

    if ProductRate.objects.filter(**filter_kwargs).exists():
        raise duplicate_error

    try:
        # The exists() pre-check can race a concurrent create — the OneToOne
        # constraint is the real guard, so a duplicate insert must surface as
        # the same clean 400, not a 500. atomic() keeps the failed insert on
        # a savepoint so the surrounding transaction stays usable.
        with transaction.atomic():
            rate = ProductRate.objects.create(
                selling_price=selling_price,
                created_by=user,
                updated_by=user,
                **filter_kwargs,
            )
    except IntegrityError:
        raise duplicate_error

    # Log the initial price setting as first history entry
    _log_rate_history(product=product, selling_price=selling_price, user=user, note=note or "Initial price set.")
    remove_from_unpriced_queue(product)
    return rate


@transaction.atomic
def update_rate(*, pk: int, selling_price: Decimal, user, note: str = "") -> ProductRate:
    """
    Update the current selling price of an existing ProductRate.
    Always logs the change into ProductRateHistory in the same transaction —
    a price change without its history row would make billing (which
    snapshots prices from history) disagree with the rates page.
    """
    rate = get_rate_by_id(pk)

    rate.selling_price = selling_price
    rate.updated_by = user
    rate.save(update_fields=["selling_price", "updated_by", "updated_at"])

    _log_rate_history(
        product=rate.product,
        selling_price=selling_price,
        user=user,
        note=note,
    )
    return rate


def update_rate_by_product(*, rm_product_id: int = None, fg_product_id: int = None, selling_price: Decimal, user, note: str = "") -> ProductRate:
    """
    Convenience service: update rate using a product id instead of rate pk.
    Useful for bulk update flows where only product ids are available.
    Delegates to update_rate to keep logic DRY.
    """
    rate = get_rate_by_product_id(rm_product_id=rm_product_id, fg_product_id=fg_product_id)
    return update_rate(pk=rate.pk, selling_price=selling_price, user=user, note=note)
