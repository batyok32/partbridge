"""
Downloads Unsplash images for all part categories and bundle categories.

Usage:
    python manage.py seed_category_images           # skip already-filled
    python manage.py seed_category_images --overwrite
"""
import ssl
import urllib.request

from django.core.files.base import ContentFile

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE
from django.core.management.base import BaseCommand

from bundles.models import BundleCategory
from parts.models import Category

# Same Unsplash CDN base used in seed.py
_BASE = "https://images.unsplash.com/photo-"
_PARAMS = "?w=800&q=80&fit=crop&auto=format"

# Each photo ID is taken from the seed.py PART_PHOTOS / CAR_PHOTOS lists
# and matched to the closest category subject.
CATEGORY_PHOTOS = {
    # ── top-level ──────────────────────────────────────────────────────────
    "engine":         "1486262715619-67b85e0b08d3",  # engine bay / workshop
    "transmission":   "1486262715619-67b85e0b08d3",  # mechanical/engine
    "suspension":     "1512341689857-198e7e2f3ca8",  # car body/chassis
    "brakes":         "1558618666-fcd25c85cd64",     # brake disc close-up
    "exterior":       "1512341689857-198e7e2f3ca8",  # car body panels
    "interior":       "1568605114967-8130f3a36994",  # car interior
    "electrical":     "1558618666-fcd25c85cd64",      # car part close-up
    "cooling":        "1530046339160-ce3e530c7d2f",  # cooling system
    "exhaust":        "1494976388531-d1058494cdd8",  # exhaust pipes
    "lighting":       "1494976388531-d1058494cdd8",  # car lights/exhaust
    "wheels":         "1503376780353-7e6692767b70",  # alloy wheel
    # ── engine children ────────────────────────────────────────────────────
    "engine-block":   "1486262715619-67b85e0b08d3",
    "cylinder-head":  "1486262715619-67b85e0b08d3",
    "turbocharger":   "1486262715619-67b85e0b08d3",
    "engine-mounts":  "1486262715619-67b85e0b08d3",
    # ── suspension children ────────────────────────────────────────────────
    "control-arms":   "1512341689857-198e7e2f3ca8",
    "struts":         "1512341689857-198e7e2f3ca8",
    # ── lighting children ──────────────────────────────────────────────────
    "headlights":     "1530046339160-ce3e530c7d2f",
    "taillights":     "1511919884226-fd3cad34687c",
    "fog-lights":     "1494976388531-d1058494cdd8",
    # ── exterior children ──────────────────────────────────────────────────
    "front-bumper":   "1512341689857-198e7e2f3ca8",
    "rear-bumper":    "1541348263662-e068662d82af",
    "fender":         "1512341689857-198e7e2f3ca8",
    "hood":           "1449824913935-59a10b8d2000",
    "door":           "1525609004556-c46c7d6cf023",
    "mirror":         "1512341689857-198e7e2f3ca8",
    # ── interior children ──────────────────────────────────────────────────
    "seat":           "1568605114967-8130f3a36994",
    "dashboard":      "1568605114967-8130f3a36994",
    "steering-wheel": "1502877338535-766e1452684a",
    "center-console": "1568605114967-8130f3a36994",
    # ── cooling children ───────────────────────────────────────────────────
    "radiator":       "1530046339160-ce3e530c7d2f",
    # ── brakes children ────────────────────────────────────────────────────
    "brake-caliper":  "1558618666-fcd25c85cd64",
    "brake-rotor":    "1558618666-fcd25c85cd64",
    # ── electrical children ────────────────────────────────────────────────
    "alternator":     "1558618666-fcd25c85cd64",
    "starter":        "1558618666-fcd25c85cd64",
    "ecu":            "1558618666-fcd25c85cd64",
}

# Bundle category photos keyed by BundleCategory.type as fallback,
# and by name for exact matches.
BUNDLE_CATEGORY_PHOTOS_BY_NAME = {}
BUNDLE_CATEGORY_PHOTOS_BY_TYPE = {
    "assembly": "1494976388531-d1058494cdd8",  # car lighting/assembly
    "discount":  "1558618666-fcd25c85cd64",    # parts value pack
}


def _download(photo_id):
    url = f"{_BASE}{photo_id}{_PARAMS}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; PartBridge-seeder/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=20, context=_SSL_CTX) as resp:
        return resp.read()


class Command(BaseCommand):
    help = "Seed category images from Unsplash (skips already-filled unless --overwrite)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--overwrite", action="store_true",
            help="Replace images that already exist.",
        )

    def handle(self, *args, **options):
        overwrite = options["overwrite"]
        ok = skip = fail = 0

        self.stdout.write(self.style.HTTP_INFO("\nPart categories"))
        for cat in Category.objects.order_by("sort_order", "name"):
            if cat.image and not overwrite:
                self.stdout.write(f"  skip  {cat.slug}")
                skip += 1
                continue
            photo_id = CATEGORY_PHOTOS.get(cat.slug)
            if not photo_id:
                self.stdout.write(self.style.WARNING(f"  skip  {cat.slug}  (no mapping)"))
                skip += 1
                continue
            try:
                data = _download(photo_id)
                cat.image.save(f"{cat.slug}.jpg", ContentFile(data), save=True)
                self.stdout.write(self.style.SUCCESS(f"  ✓     {cat.slug}"))
                ok += 1
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"  ✗     {cat.slug}: {exc}"))
                fail += 1

        self.stdout.write(self.style.HTTP_INFO("\nBundle categories"))
        for bcat in BundleCategory.objects.all():
            if bcat.image and not overwrite:
                self.stdout.write(f"  skip  {bcat.name!r}")
                skip += 1
                continue
            photo_id = (
                BUNDLE_CATEGORY_PHOTOS_BY_NAME.get(bcat.name)
                or BUNDLE_CATEGORY_PHOTOS_BY_TYPE.get(bcat.type)
            )
            if not photo_id:
                self.stdout.write(self.style.WARNING(f"  skip  {bcat.name!r}  (no mapping)"))
                skip += 1
                continue
            try:
                data = _download(photo_id)
                safe = bcat.name.lower().replace(" ", "-")
                bcat.image.save(f"bundle-cat-{safe}.jpg", ContentFile(data), save=True)
                self.stdout.write(self.style.SUCCESS(f"  ✓     {bcat.name!r}"))
                ok += 1
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"  ✗     {bcat.name!r}: {exc}"))
                fail += 1

        self.stdout.write(
            f"\n{ok} saved, {skip} skipped, {fail} failed"
        )
