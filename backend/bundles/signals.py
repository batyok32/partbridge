from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Bundle, BundleCategory, BundleItem


def _sync_assembly_item(bundle_pk):
    from parts.models import Item

    try:
        bundle = Bundle.objects.select_related("bundle_category").get(pk=bundle_pk)
    except Bundle.DoesNotExist:
        return

    if bundle.bundle_category.type != BundleCategory.BundleType.ASSEMBLY:
        return

    bundle_items = list(
        BundleItem.objects.filter(bundle=bundle).select_related(
            "item__vehicle", "item__category"
        )
    )
    is_active = bundle.status == Bundle.Status.ACTIVE

    assembly_item = Item.objects.filter(assembly_bundle=bundle).first()

    if not bundle_items:
        if assembly_item and assembly_item.status != Item.Status.SOLD:
            target = Item.Status.ACTIVE if is_active else Item.Status.REMOVED
            Item.objects.filter(pk=assembly_item.pk).update(status=target)
        return

    first_item = next((bi.item for bi in bundle_items if bi.item and bi.item.vehicle), None)
    if not first_item:
        return

    if bundle.fixed_price:
        price = bundle.fixed_price
    else:
        total = sum(float(bi.item.price) for bi in bundle_items if bi.item)
        discount = float(bundle.discount_pct or 0)
        price = round(total * (1 - discount / 100), 2)

    item_status = Item.Status.ACTIVE if is_active else Item.Status.REMOVED
    # Use explicitly chosen category; fall back to first component item's category
    category = bundle.category if bundle.category_id else first_item.category

    if assembly_item:
        if assembly_item.status != Item.Status.SOLD:
            Item.objects.filter(pk=assembly_item.pk).update(
                title=bundle.name, price=price, status=item_status, category=category,
            )
    else:
        assembly_item = Item(
            vehicle=first_item.vehicle,
            category=category,
            title=bundle.name,
            price=price,
            condition=first_item.condition,
            shipping_size=first_item.shipping_size,
            status=item_status,
            assembly_bundle=bundle,
        )
        assembly_item.save()

    component_ids = [
        bi.item_id for bi in bundle_items
        if bi.item_id and bi.item_id != assembly_item.pk
    ]
    if is_active:
        Item.objects.filter(id__in=component_ids, status=Item.Status.ACTIVE).update(
            status=Item.Status.HIDDEN_IN_ASSEMBLY
        )
        # Remove any existing CartItems pointing to now-hidden component items
        from orders.models import CartItem
        CartItem.objects.filter(item_id__in=component_ids).delete()
    else:
        Item.objects.filter(id__in=component_ids, status=Item.Status.HIDDEN_IN_ASSEMBLY).update(
            status=Item.Status.ACTIVE
        )


@receiver(post_save, sender=Bundle)
def on_bundle_save(sender, instance, **kwargs):
    _sync_assembly_item(instance.pk)


@receiver(post_save, sender=BundleItem)
def on_bundle_item_save(sender, instance, **kwargs):
    _sync_assembly_item(instance.bundle_id)


@receiver(post_delete, sender=BundleItem)
def on_bundle_item_delete(sender, instance, **kwargs):
    from parts.models import Item
    Item.objects.filter(pk=instance.item_id, status=Item.Status.HIDDEN_IN_ASSEMBLY).update(
        status=Item.Status.ACTIVE
    )
    _sync_assembly_item(instance.bundle_id)
