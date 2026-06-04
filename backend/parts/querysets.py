from django.db.models import Q

from .models import Item, ItemCompatibility


def active_items_qs():
    return (
        Item.objects.filter(status=Item.Status.ACTIVE)
        .select_related("category", "vehicle__generation__car_model__make", "vehicle__seller")
        .prefetch_related("photos", "compatibilities", "alt_part_numbers")
    )


def filter_items_by_car(qs, *, generation_id=None, modification_id=None, compatible_only=False):
    if not generation_id:
        return qs
    if compatible_only:
        compat_q = Q(compatibilities__generation_id=generation_id)
        if modification_id:
            compat_q &= Q(compatibilities__modification_id=modification_id) | Q(
                compatibilities__modification__isnull=True
            )
        qs = qs.filter(compat_q).distinct()
    return qs


def item_fitment_status(item, *, generation_id=None, modification_id=None):
    if not generation_id:
        return None
    compat_qs = item.compatibilities.filter(generation_id=generation_id)
    if modification_id:
        compat_qs = compat_qs.filter(
            Q(modification_id=modification_id) | Q(modification__isnull=True)
        )
    if compat_qs.exists():
        best = compat_qs.order_by("-confidence_score").first()
        return {"status": "fits", "confidence_score": best.confidence_score if best else None}
    return {"status": "unknown", "confidence_score": None}
