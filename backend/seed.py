#!/usr/bin/env python
"""
Full database seed script.
Run from the backend directory:
    python seed.py
"""
import os, sys, random, datetime

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django; django.setup()

from django.utils import timezone
from django.db import transaction

from accounts.models import ShippingAddress, User, UserCar
from bundles.models import Bundle, BundleCategory, BundleItem
from catalog.models import CarModel, Generation, Make, Modification
from messaging.models import Message, Thread
from orders.models import (
    CartItem, Dispute, DisputeMessage, Order, OrderItem,
    Payment, SellerReview, ShippingRequest,
)
from parts.models import (
    Category, Item, ItemCompatibility, ItemPhoto,
    Option, OptionCategory, OptionValue, PartNumber, Variation,
)
from vehicles.models import Vehicle, VehiclePhoto

rng = random.Random(42)

def pick(lst): return rng.choice(lst)
def picks(lst, k): return rng.sample(lst, min(k, len(lst)))
def pct(p): return rng.random() < p

def ago(**kw):
    return timezone.now() - datetime.timedelta(**kw)

def date_between(start_year, end_year):
    y = rng.randint(start_year, end_year)
    m = rng.randint(1, 12)
    d = rng.randint(1, 28)
    return datetime.date(y, m, d)

# ─── catalog ─────────────────────────────────────────────────────────────────

MAKES_DATA = [
    ("BMW",          "DE", "https://cdn.partbridge.com/makes/bmw.svg"),
    ("Mercedes-Benz","DE", "https://cdn.partbridge.com/makes/mercedes.svg"),
    ("Toyota",       "JP", "https://cdn.partbridge.com/makes/toyota.svg"),
    ("Honda",        "JP", "https://cdn.partbridge.com/makes/honda.svg"),
    ("Ford",         "US", "https://cdn.partbridge.com/makes/ford.svg"),
    ("Chevrolet",    "US", "https://cdn.partbridge.com/makes/chevy.svg"),
    ("Audi",         "DE", "https://cdn.partbridge.com/makes/audi.svg"),
    ("Volkswagen",   "DE", "https://cdn.partbridge.com/makes/vw.svg"),
    ("Subaru",       "JP", "https://cdn.partbridge.com/makes/subaru.svg"),
    ("Nissan",       "JP", "https://cdn.partbridge.com/makes/nissan.svg"),
]

MODELS_DATA = {
    "BMW": [("3 Series","3-series"),("5 Series","5-series"),("X5","x5"),("M3","m3")],
    "Mercedes-Benz": [("C-Class","c-class"),("E-Class","e-class"),("GLE","gle")],
    "Toyota": [("Camry","camry"),("Corolla","corolla"),("Tacoma","tacoma"),("4Runner","4runner")],
    "Honda": [("Civic","civic"),("Accord","accord"),("CR-V","cr-v")],
    "Ford": [("F-150","f-150"),("Mustang","mustang"),("Explorer","explorer")],
    "Chevrolet": [("Silverado","silverado"),("Camaro","camaro"),("Tahoe","tahoe")],
    "Audi": [("A4","a4"),("A6","a6"),("Q5","q5")],
    "Volkswagen": [("Golf","golf"),("Jetta","jetta"),("Tiguan","tiguan")],
    "Subaru": [("Impreza","impreza"),("WRX","wrx"),("Outback","outback")],
    "Nissan": [("Altima","altima"),("Maxima","maxima"),("Frontier","frontier")],
}

GENERATIONS_DATA = {
    "BMW 3 Series": [
        ("E46", ["E46"],              datetime.date(1998,1,1), datetime.date(2006,12,31)),
        ("E90", ["E90","E91","E92","E93"], datetime.date(2005,1,1), datetime.date(2013,12,31)),
        ("F30", ["F30","F31","F34"], datetime.date(2012,1,1), datetime.date(2019,12,31)),
        ("G20", ["G20","G21"],       datetime.date(2019,1,1), None),
    ],
    "BMW 5 Series": [
        ("E39", ["E39"], datetime.date(1995,1,1), datetime.date(2004,12,31)),
        ("E60", ["E60","E61"], datetime.date(2003,1,1), datetime.date(2010,12,31)),
        ("F10", ["F10","F11"], datetime.date(2010,1,1), datetime.date(2017,12,31)),
    ],
    "BMW X5": [
        ("E53", ["E53"], datetime.date(1999,1,1), datetime.date(2006,12,31)),
        ("E70", ["E70"], datetime.date(2006,1,1), datetime.date(2013,12,31)),
        ("F15", ["F15"], datetime.date(2013,1,1), datetime.date(2018,12,31)),
    ],
    "Toyota Camry": [
        ("XV30", ["XV30"], datetime.date(2002,1,1), datetime.date(2006,12,31)),
        ("XV40", ["XV40"], datetime.date(2007,1,1), datetime.date(2011,12,31)),
        ("XV50", ["XV50"], datetime.date(2012,1,1), datetime.date(2017,12,31)),
        ("XV70", ["XV70"], datetime.date(2018,1,1), None),
    ],
    "Honda Civic": [
        ("8th Gen", ["FA","FD"], datetime.date(2006,1,1), datetime.date(2011,12,31)),
        ("9th Gen", ["FB","FG"], datetime.date(2012,1,1), datetime.date(2015,12,31)),
        ("10th Gen",["FC","FK"], datetime.date(2016,1,1), datetime.date(2021,12,31)),
        ("11th Gen",["FL"],      datetime.date(2022,1,1), None),
    ],
    "Ford F-150": [
        ("12th Gen", ["P3"],   datetime.date(2009,1,1), datetime.date(2014,12,31)),
        ("13th Gen", ["P552"], datetime.date(2015,1,1), datetime.date(2020,12,31)),
        ("14th Gen", ["P702"], datetime.date(2021,1,1), None),
    ],
    "Subaru WRX": [
        ("GD/GG", ["GD","GG"], datetime.date(2001,1,1), datetime.date(2007,12,31)),
        ("GE/GH", ["GE","GH"], datetime.date(2008,1,1), datetime.date(2014,12,31)),
        ("VA",    ["VA"],      datetime.date(2015,1,1), datetime.date(2021,12,31)),
        ("VB",    ["VB"],      datetime.date(2022,1,1), None),
    ],
}

# ─── part categories ──────────────────────────────────────────────────────────

CATEGORIES_DATA = [
    # (name, slug, parent_slug, sort_order, shipping_size)
    ("Engine",         "engine",        None,         1, "large"),
    ("Transmission",   "transmission",  None,         2, "large"),
    ("Suspension",     "suspension",    None,         3, "medium"),
    ("Brakes",         "brakes",        None,         4, "small"),
    ("Exterior",       "exterior",      None,         5, "medium"),
    ("Interior",       "interior",      None,         6, "medium"),
    ("Electrical",     "electrical",    None,         7, "small"),
    ("Cooling",        "cooling",       None,         8, "medium"),
    ("Exhaust",        "exhaust",       None,         9, "medium"),
    ("Lighting",       "lighting",      None,        10, "medium"),
    ("Wheels & Tires", "wheels",        None,        11, "large"),
    # children
    ("Engine Block",    "engine-block",   "engine",      1, "xl"),
    ("Cylinder Head",   "cylinder-head",  "engine",      2, "large"),
    ("Turbocharger",    "turbocharger",   "engine",      3, "medium"),
    ("Engine Mounts",   "engine-mounts",  "engine",      4, "small"),
    ("Control Arms",    "control-arms",   "suspension",  1, "medium"),
    ("Struts & Shocks", "struts",         "suspension",  2, "medium"),
    ("Headlights",      "headlights",     "lighting",    1, "medium"),
    ("Taillights",      "taillights",     "lighting",    2, "medium"),
    ("Fog Lights",      "fog-lights",     "lighting",    3, "small"),
    ("Front Bumper",    "front-bumper",   "exterior",    1, "large"),
    ("Rear Bumper",     "rear-bumper",    "exterior",    2, "large"),
    ("Fender",          "fender",         "exterior",    3, "medium"),
    ("Hood",            "hood",           "exterior",    4, "large"),
    ("Door",            "door",           "exterior",    5, "xl"),
    ("Mirror",          "mirror",         "exterior",    6, "small"),
    ("Seat",            "seat",           "interior",    1, "large"),
    ("Dashboard",       "dashboard",      "interior",    2, "large"),
    ("Steering Wheel",  "steering-wheel", "interior",    3, "medium"),
    ("Center Console",  "center-console", "interior",    4, "medium"),
    ("Radiator",        "radiator",       "cooling",     1, "large"),
    ("Brake Caliper",   "brake-caliper",  "brakes",      1, "small"),
    ("Brake Rotor",     "brake-rotor",    "brakes",      2, "medium"),
    ("Alternator",      "alternator",     "electrical",  1, "small"),
    ("Starter Motor",   "starter",        "electrical",  2, "small"),
    ("ECU",             "ecu",            "electrical",  3, "small"),
]

# (category_slug, name, type, is_required, predefined_values)
OPTION_CATEGORIES_DATA = [
    ("headlights",   "Side",      "side",     True,  ["Left", "Right"]),
    ("headlights",   "Bulb type", "other",    False, ["Xenon", "LED", "Halogen"]),
    ("taillights",   "Side",      "side",     True,  ["Left", "Right"]),
    ("taillights",   "Type",      "other",    False, ["LED", "Standard"]),
    ("fog-lights",   "Side",      "side",     True,  ["Left", "Right"]),
    ("mirror",       "Side",      "side",     True,  ["Left", "Right"]),
    ("fender",       "Side",      "side",     True,  ["Left", "Right"]),
    ("door",         "Side",      "side",     True,  ["Front Left", "Front Right", "Rear Left", "Rear Right"]),
    ("seat",         "Position",  "position", True,  ["Driver", "Passenger", "Rear Left", "Rear Center", "Rear Right"]),
    ("brake-caliper","Corner",    "position", True,  ["Front Left", "Front Right", "Rear Left", "Rear Right"]),
    ("struts",       "Corner",    "position", True,  ["Front Left", "Front Right", "Rear Left", "Rear Right"]),
    ("control-arms", "Position",  "position", True,  ["Front Left", "Front Right", "Rear Left", "Rear Right"]),
    ("front-bumper", "Color",     "color",    False, ["Black", "White", "Silver", "Gray", "Primed"]),
    ("rear-bumper",  "Color",     "color",    False, ["Black", "White", "Silver", "Gray", "Primed"]),
]

ITEM_TEMPLATES = {
    "headlights":     [("Headlight Assembly",   25,  350, "medium")],
    "taillights":     [("Taillight Assembly",   20,  280, "medium")],
    "fog-lights":     [("Fog Light Assembly",   15,  120, "small")],
    "mirror":         [("Side Mirror Assembly", 20,  180, "small")],
    "front-bumper":   [("Front Bumper Cover",   60,  600, "large")],
    "rear-bumper":    [("Rear Bumper Cover",    55,  550, "large")],
    "fender":         [("Front Fender Panel",   50,  400, "medium")],
    "hood":           [("Hood Panel",           80,  700, "large")],
    "door":           [("Door Assembly",        100, 900, "xl")],
    "control-arms":   [("Control Arm",          40,  350, "medium"), ("Rear Control Arm", 35, 300, "medium")],
    "struts":         [("Front Strut Assembly", 60,  400, "medium"), ("Rear Shock Absorber", 50, 350, "medium")],
    "brake-caliper":  [("Brake Caliper",        30,  200, "small")],
    "brake-rotor":    [("Brake Rotor",          25,  150, "medium")],
    "radiator":       [("Radiator Assembly",    80,  450, "large")],
    "turbocharger":   [("Turbocharger",        150, 1200, "medium")],
    "engine-block":   [("Engine Block",        300, 3500, "xl")],
    "cylinder-head":  [("Cylinder Head",       200, 1800, "large")],
    "engine-mounts":  [("Engine Mount Set",     30,  200, "small")],
    "alternator":     [("Alternator",           40,  280, "small")],
    "starter":        [("Starter Motor",        45,  250, "small")],
    "ecu":            [("Engine Control Unit", 100,  800, "small")],
    "seat":           [("Front Seat",           80,  600, "large")],
    "dashboard":      [("Dashboard Assembly",  150, 1200, "large")],
    "steering-wheel": [("Steering Wheel",       30,  250, "medium")],
    "center-console": [("Center Console",       50,  400, "medium")],
}

CONDITION_WEIGHTS = [("excellent",0.15),("good",0.50),("fair",0.30),("for_parts",0.05)]
CONDITIONS = [c for c,_ in CONDITION_WEIGHTS]
COND_W     = [w for _,w in CONDITION_WEIGHTS]

ITEM_DESCRIPTIONS = [
    "Removed from a low-mileage donor vehicle. Tested and confirmed working before removal. No cracks or damage.",
    "Good condition, minor surface scratches from normal use. Fully functional. Fits as listed.",
    "Pulled from a collision vehicle — the part itself is undamaged. Please verify fitment for your specific trim.",
    "OEM part in excellent condition. This was on a daily driver with regular maintenance.",
    "Fair condition with some cosmetic wear. Structurally sound and fully functional.",
    "Clean part with no issues. Donor car had this replaced preventatively before it failed.",
    "Used but in great shape. Matching OEM part number where applicable.",
    "Genuine factory part. Removed during engine swap — the part itself is not the reason for the swap.",
]

SELLER_ZIPS_STATES = [
    ("90210","CA"),("98101","WA"),("77001","TX"),("30301","GA"),
    ("10001","NY"),("60601","IL"),("85001","AZ"),("97201","OR"),
    ("33101","FL"),("75201","TX"),
]
BUYER_ZIPS  = ["94102","78201","19101","48201","80202","37201","27601","32801","40202","64101"]
US_STATES   = ["CA","WA","TX","GA","NY","IL","AZ","OR","FL","MI","CO","TN","NC","MO"]

FIRST_NAMES = ["James","Emily","Michael","Sarah","David","Jessica","Chris","Laura","Ryan","Ashley",
               "Daniel","Megan","Tyler","Heather","Brandon","Amanda","Alex","Rachel","Kevin","Stephanie"]
LAST_NAMES  = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Wilson","Taylor",
               "Anderson","Thomas","Moore","Martin","Jackson","Thompson","White","Harris","Clark","Lewis"]

PHOTO_BASE = "https://images.unsplash.com/photo-"
PART_PHOTOS = [
    "1558618666-fcd25c85cd64?w=800",
    "1486262715619-67b85e0b08d3?w=800",
    "1504222994343-536c8c7e6bc6?w=800",
    "1600712242865-5a609e3a9b40?w=800",
    "1512341689857-198e7e2f3ca8?w=800",
    "1568605114967-8130f3a36994?w=800",
    "1603584173870-7f23c33a68d0?w=800",
    "1530046339160-ce3e530c7d2f?w=800",
    "1574169208547-cbee3e5c2fc2?w=800",
]
CAR_PHOTOS = [
    "1494976388531-d1058494cdd8?w=800",
    "1503376780353-7e6692767b70?w=800",
    "1552519507-da3b142936bc?w=800",
    "1511919884226-fd3cad34687c?w=800",
    "1541348263662-e068662d82af?w=800",
    "1449824913935-59a10b8d2000?w=800",
    "1502877338535-766e1452684a?w=800",
    "1525609004556-c46c7d6cf023?w=800",
]

# ─── clear ────────────────────────────────────────────────────────────────────

print("Clearing existing data…")
with transaction.atomic():
    DisputeMessage.objects.all().delete()
    Dispute.objects.all().delete()
    SellerReview.objects.all().delete()
    ShippingRequest.objects.all().delete()
    Message.objects.all().delete()
    Thread.objects.all().delete()
    OrderItem.objects.all().delete()
    Payment.objects.all().delete()
    Order.objects.all().delete()
    CartItem.objects.all().delete()
    BundleItem.objects.all().delete()
    Bundle.objects.all().delete()
    BundleCategory.objects.all().delete()
    Variation.objects.all().delete()
    ItemCompatibility.objects.all().delete()
    PartNumber.objects.all().delete()
    Option.objects.all().delete()
    ItemPhoto.objects.all().delete()
    Item.objects.all().delete()
    OptionValue.objects.all().delete()
    OptionCategory.objects.all().delete()
    Category.objects.all().delete()
    VehiclePhoto.objects.all().delete()
    Vehicle.objects.all().delete()
    UserCar.objects.all().delete()
    ShippingAddress.objects.all().delete()
    User.objects.filter(is_superuser=False).delete()
    Modification.objects.all().delete()
    Generation.objects.all().delete()
    CarModel.objects.all().delete()
    Make.objects.all().delete()

# ── 1. catalog ────────────────────────────────────────────────────────────────

print("Creating catalog…")
makes = {}
for name, country, logo in MAKES_DATA:
    m = Make.objects.create(
        name=name,
        slug=name.lower().replace(" ", "-"),
        country=country,
        logo_url=logo,
    )
    makes[name] = m

car_models = {}
for make_name, model_list in MODELS_DATA.items():
    for model_name, slug in model_list:
        cm = CarModel.objects.create(make=makes[make_name], name=model_name, slug=slug)
        car_models[f"{make_name} {model_name}"] = cm

generations = {}
for key, gen_list in GENERATIONS_DATA.items():
    cm = car_models[key]
    for gen_name, codes, start, end in gen_list:
        g = Generation.objects.create(
            car_model=cm, make=cm.make, name=gen_name, chassis_codes=codes,
            production_start=start, production_end=end,
            body_style=pick(["sedan","coupe","wagon","hatchback","suv","truck"]),
        )
        generations[f"{key} {gen_name}"] = g

E90 = generations.get("BMW 3 Series E90")
if E90:
    for code, engine, fuel, hp, start, end in [
        ("320i","N46","gasoline",150, datetime.date(2005,1,1), datetime.date(2011,12,31)),
        ("325i","N52","gasoline",218, datetime.date(2005,1,1), datetime.date(2011,12,31)),
        ("330i","N53","gasoline",272, datetime.date(2005,1,1), datetime.date(2011,12,31)),
        ("335i","N54","gasoline",306, datetime.date(2007,1,1), datetime.date(2013,12,31)),
        ("335d","M57","diesel",  286, datetime.date(2007,1,1), datetime.date(2011,12,31)),
        ("M3",  "S65","gasoline",420, datetime.date(2007,1,1), datetime.date(2013,12,31)),
    ]:
        Modification.objects.create(
            generation=E90, code=code, engine_code=engine, fuel_type=fuel,
            power_hp=hp, production_start=start, production_end=end,
        )

CIV10 = generations.get("Honda Civic 10th Gen")
if CIV10:
    for code, engine, fuel, hp, start, end in [
        ("LX",    "R18",  "gasoline",158, datetime.date(2016,1,1), datetime.date(2021,12,31)),
        ("Sport", "L15B", "gasoline",174, datetime.date(2016,1,1), datetime.date(2021,12,31)),
        ("Si",    "K20C", "gasoline",205, datetime.date(2017,1,1), datetime.date(2021,12,31)),
        ("Type R","K20C1","gasoline",306, datetime.date(2017,1,1), datetime.date(2021,12,31)),
    ]:
        Modification.objects.create(
            generation=CIV10, code=code, engine_code=engine, fuel_type=fuel,
            power_hp=hp, production_start=start, production_end=end,
        )

all_generations = list(generations.values())
print(f"  {len(makes)} makes, {len(car_models)} models, {len(all_generations)} generations")

# ── 2. categories & option categories ────────────────────────────────────────

print("Creating categories and option categories…")
cat_by_slug = {}
for name, slug, parent_slug, sort, size in CATEGORIES_DATA:
    parent = cat_by_slug.get(parent_slug)
    c = Category.objects.create(name=name, slug=slug, parent=parent, sort_order=sort, shipping_size_default=size)
    cat_by_slug[slug] = c

# opt_cats_by_slug: slug → list of OptionCategory
opt_cats_by_slug = {}
for cat_slug, name, otype, is_required, values in OPTION_CATEGORIES_DATA:
    cat = cat_by_slug.get(cat_slug)
    if not cat:
        continue
    oc = OptionCategory.objects.create(category=cat, name=name, type=otype, is_required=is_required)
    for i, v in enumerate(values):
        OptionValue.objects.create(option_category=oc, value=v, sort_order=i)
    opt_cats_by_slug.setdefault(cat_slug, []).append(oc)

# ── 3. users ──────────────────────────────────────────────────────────────────

print("Creating users…")
sellers, buyers = [], []

if not User.objects.filter(email="admin@partbridge.com").exists():
    admin = User.objects.create_superuser(email="admin@partbridge.com", password="admin1234")
    admin.first_name = "Admin"; admin.last_name = "PartBridge"
    admin.email_verified_at = timezone.now(); admin.save()
    print("  admin@partbridge.com / admin1234")

for i in range(8):
    fn, ln = FIRST_NAMES[i], LAST_NAMES[i]
    u = User.objects.create_user(email=f"seller{i+1}@example.com", password="password123",
                                  first_name=fn, last_name=ln)
    u.is_seller = True
    u.email_verified_at = ago(days=rng.randint(30,600))
    u.date_joined = ago(days=rng.randint(30,600))
    u.save()
    zip_, state = pick(SELLER_ZIPS_STATES)
    ShippingAddress.objects.create(user=u, full_name=f"{fn} {ln}",
        line1=f"{rng.randint(100,9999)} Oak St", city="Portland",
        state=state, zip=zip_, is_default=True)
    sellers.append(u)

for i in range(15):
    fn = FIRST_NAMES[(8 + i) % len(FIRST_NAMES)]
    ln = LAST_NAMES[(8 + i) % len(LAST_NAMES)]
    u = User.objects.create_user(email=f"buyer{i+1}@example.com", password="password123",
                                  first_name=fn, last_name=ln)
    u.email_verified_at = ago(days=rng.randint(1,400))
    u.date_joined = ago(days=rng.randint(1,400))
    u.save()
    ShippingAddress.objects.create(user=u, full_name=f"{fn} {ln}",
        line1=f"{rng.randint(100,9999)} Maple Ave",
        city=pick(["Seattle","Austin","Miami","Chicago","Denver"]),
        state=pick(US_STATES), zip=pick(BUYER_ZIPS), is_default=True)
    gen = pick(all_generations)
    start_yr = gen.production_start.year
    end_yr   = gen.production_end.year if gen.production_end else 2024
    UserCar.objects.create(user=u, generation=gen,
        year=rng.randint(start_yr, min(end_yr, 2024)), is_default=True)
    buyers.append(u)

print(f"  {len(sellers)} sellers, {len(buyers)} buyers")

# ── 4. vehicles & items ───────────────────────────────────────────────────────

print("Creating vehicles and parts…")
all_items = []
all_vehicles = []

OEM_PREFIXES = ["BMW","HON","TOY","FOR","CHE","AUD","VWG","SUB","NIS","MBZ"]

for seller in sellers:
    for _ in range(rng.randint(2, 4)):
        gen = pick(all_generations)
        start_yr = gen.production_start.year
        end_yr   = gen.production_end.year if gen.production_end else 2022
        year     = rng.randint(start_yr, min(end_yr, 2022))
        mods     = list(gen.modifications.all())
        mod      = pick(mods) if mods else None
        zip_, state = pick(SELLER_ZIPS_STATES)

        vehicle = Vehicle.objects.create(
            seller=seller, generation=gen, modification=mod, year=year,
            color=pick(["Black","White","Silver","Gray","Blue","Red"]),
            mileage=rng.randint(25000, 220000),
            condition=pick(["excellent","good","fair","good","good"]),
            status="active",
            seller_zip=zip_,
            seller_state=state,
            vin=f"WBA{rng.randint(10000000,99999999)}{rng.randint(100,999)}",
        )
        all_vehicles.append(vehicle)

        for j, photo_suffix in enumerate(picks(CAR_PHOTOS, rng.randint(2, 4))):
            VehiclePhoto.objects.create(
                vehicle=vehicle,
                url=PHOTO_BASE + photo_suffix,
                thumbnail_url=PHOTO_BASE + photo_suffix.replace("w=800","w=200"),
                sort_order=j, is_primary=(j==0),
                label=pick(["Front","Rear","Engine","Interior","Side"]),
            )

        slugs_to_use = picks(list(ITEM_TEMPLATES.keys()), rng.randint(4, 12))
        for slug in slugs_to_use:
            cat = cat_by_slug.get(slug)
            if not cat:
                continue
            for title_tpl, price_min, price_max, default_size in ITEM_TEMPLATES[slug]:
                make_name  = gen.car_model.make.name
                model_name = gen.car_model.name
                title = f"{year} {make_name} {model_name} {gen.name} {title_tpl}"
                price = rng.randint(price_min, price_max)
                condition = rng.choices(CONDITIONS, weights=COND_W, k=1)[0]

                if default_size == "small":
                    dims = dict(weight_lbs=rng.uniform(1,9), dim_l_in=rng.uniform(4,11), dim_w_in=rng.uniform(4,11), dim_h_in=rng.uniform(2,11))
                elif default_size == "medium":
                    dims = dict(weight_lbs=rng.uniform(10,38), dim_l_in=rng.uniform(13,47), dim_w_in=rng.uniform(8,30), dim_h_in=rng.uniform(4,20))
                elif default_size == "large":
                    dims = dict(weight_lbs=rng.uniform(40,148), dim_l_in=rng.uniform(49,95), dim_w_in=rng.uniform(20,50), dim_h_in=rng.uniform(10,30))
                else:
                    dims = dict(weight_lbs=rng.uniform(150,600), dim_l_in=rng.uniform(97,180), dim_w_in=rng.uniform(40,70), dim_h_in=rng.uniform(20,60))

                oem = f"{pick(OEM_PREFIXES)}-{rng.randint(10000,99999)}" if pct(0.5) else ""
                item = Item(vehicle=vehicle, category=cat, title=title,
                            description=pick(ITEM_DESCRIPTIONS), price=price,
                            condition=condition, oem_part_number=oem, **dims)
                item.save()

                # Photos
                for j, photo_suffix in enumerate(picks(PART_PHOTOS, rng.randint(1, 4))):
                    ItemPhoto.objects.create(
                        item=item,
                        url=PHOTO_BASE + photo_suffix,
                        thumbnail_url=PHOTO_BASE + photo_suffix.replace("w=800","w=200"),
                        sort_order=j, is_primary=(j==0),
                    )

                # Alternate part numbers (30% chance)
                if pct(0.3):
                    for brand, prefix in picks([("Bosch","BSH"),("Denso","DNS"),("NGK","NGK"),("ACDelco","ACD")], rng.randint(1,2)):
                        pn_raw = f"{prefix}-{rng.randint(10000,99999)}"
                        PartNumber.objects.create(item=item, number_raw=pn_raw, brand=brand)

                # Options — one value per option category, picked from predefined values
                for oc in opt_cats_by_slug.get(slug, []):
                    predefined = list(oc.predefined_values.values_list("value", flat=True))
                    if predefined:
                        Option.objects.create(item=item, option_category=oc, value=pick(predefined))

                # Compatibility
                compat_gens = picks(all_generations, rng.randint(1, 3))
                if gen not in compat_gens:
                    compat_gens.append(gen)
                for cgen in compat_gens:
                    score = rng.uniform(0.75, 1.0) if cgen == gen else rng.uniform(0.5, 0.9)
                    ItemCompatibility.objects.create(
                        item=item, generation=cgen,
                        confidence_score=score,
                        source="manual" if cgen == gen else "ai",
                    )

                all_items.append(item)

print(f"  {len(all_vehicles)} vehicles, {len(all_items)} items")

# ── 5. orders ─────────────────────────────────────────────────────────────────

print("Creating orders…")
order_statuses = [("delivered",0.40),("shipped",0.20),("confirmed",0.15),("pending",0.15),("cancelled",0.10)]
all_orders = []

for buyer in buyers:
    addr = buyer.shipping_addresses.first()
    if not addr:
        continue
    for _ in range(rng.randint(1, 4)):
        items_for_order = [i for i in picks(all_items, rng.randint(1,3)) if i.vehicle.seller != buyer]
        if not items_for_order:
            continue
        status = rng.choices([s for s,_ in order_statuses], weights=[w for _,w in order_statuses], k=1)[0]
        subtotal = sum(float(i.price) for i in items_for_order)
        shipping_cost = round(rng.uniform(8, 120), 2)
        total = round(subtotal + shipping_cost, 2)
        placed_at = ago(days=rng.randint(1, 365))
        order = Order.objects.create(
            buyer=buyer, shipping_address=addr, status=status,
            subtotal=subtotal, shipping_cost=shipping_cost, total=total, placed_at=placed_at,
        )
        Order.objects.filter(pk=order.pk).update(placed_at=placed_at)
        order_items_created = []
        for item in items_for_order:
            snap = {"title": item.title, "price": str(item.price),
                    "condition": item.condition, "category_name": item.category.name}
            oi = OrderItem.objects.create(order=order, item=item,
                                          price_at_purchase=item.price, item_snapshot=snap)
            order_items_created.append(oi)
            if status in ("shipped","delivered","confirmed"):
                ShippingRequest.objects.create(
                    order_item=oi, seller=item.vehicle.seller,
                    method=pick(["parcel","parcel","freight","pickup"]),
                    shipping_size=item.shipping_size,
                    origin_zip=item.vehicle.seller_zip, dest_zip=addr.zip,
                    quoted_cost=round(rng.uniform(8,90),2),
                    actual_cost=round(rng.uniform(8,90),2) if status=="delivered" else None,
                    carrier=pick(["UPS","FedEx","USPS"]),
                    tracking_number=f"1Z{rng.randint(100000000,999999999)}" if status in ("shipped","delivered") else "",
                    is_delivered=(status=="delivered"),
                    delivered_at=ago(days=rng.randint(1,30)) if status=="delivered" else None,
                )
        if status != "cancelled":
            pay_status = "captured" if status in ("shipped","delivered","confirmed") else "pending"
            Payment.objects.create(order=order, status=pay_status, amount=total, provider="stripe",
                provider_reference=f"pi_{rng.randint(10**15,10**16-1)}", payment_method="card",
                paid_at=ago(days=rng.randint(1,300)) if pay_status=="captured" else None)
        if status == "delivered":
            for oi in order_items_created:
                if pct(0.7):
                    SellerReview.objects.create(
                        order_item=oi, buyer=buyer, seller=oi.item.vehicle.seller,
                        rating=rng.choices([5,4,3,2,1], weights=[55,25,10,6,4], k=1)[0],
                        body=pick(["Great seller, part was exactly as described!",
                                   "Fast shipping and well packaged. Would buy again.",
                                   "Part works great, very happy with the purchase.",
                                   "Good communication. The part fit perfectly.",
                                   "Excellent condition. Saved me a ton over dealer pricing.",
                                   "Part was as described. Solid transaction.", ""]),
                    )
        all_orders.append(order)

# ── 6. cart items ─────────────────────────────────────────────────────────────

print("Creating cart items…")
active_items = [i for i in all_items if i.status == "active"]
for buyer in picks(buyers, min(8, len(buyers))):
    for item in picks(active_items, rng.randint(1,3)):
        if item.vehicle.seller != buyer:
            CartItem.objects.get_or_create(user=buyer, item=item)

# ── 7. disputes ───────────────────────────────────────────────────────────────

print("Creating disputes…")
delivered_ois = list(OrderItem.objects.filter(order__status="delivered")
                     .select_related("order__buyer","item__vehicle__seller")[:40])
for oi in picks(delivered_ois, min(6, len(delivered_ois))):
    reason = pick(["not_as_described","wrong_part","not_received","damaged","other"])
    status = pick(["open","under_review","resolved_refund","resolved_no_action"])
    d = Dispute.objects.create(
        order_item=oi, buyer=oi.order.buyer, seller=oi.item.vehicle.seller,
        reason=reason,
        description=pick(["The part does not match what was listed.",
                           "I received the wrong part.",
                           "Item never arrived.",
                           "Part arrived cracked and unusable.",
                           "Description said excellent but has significant damage."]),
        status=status,
        resolution="Partial refund issued." if "resolved" in status else "",
        refund_amount=rng.randint(20,200) if status=="resolved_refund" else None,
        opened_at=ago(days=rng.randint(1,60)),
        resolved_at=ago(days=rng.randint(1,30)) if "resolved" in status else None,
    )
    msgs = [
        ("buyer",   "I opened this dispute. Please see my description above."),
        ("seller",  "Sorry to hear about the issue. Can you send photos?"),
        ("buyer",   "I've sent the photos. You can see the damage clearly."),
        ("support", "We've reviewed the evidence and will issue a resolution shortly."),
    ]
    for role, body in picks(msgs, rng.randint(1, len(msgs))):
        sender = oi.order.buyer if role == "buyer" else oi.item.vehicle.seller
        DisputeMessage.objects.create(dispute=d, sender=sender, sender_role=role, body=body)

# ── 8. message threads ────────────────────────────────────────────────────────

print("Creating message threads…")
for _ in range(20):
    buyer  = pick(buyers)
    item   = pick(active_items)
    seller = item.vehicle.seller
    if buyer == seller:
        continue
    thread = Thread.objects.create(buyer=buyer, seller=seller, item=item,
                                    last_message_at=ago(days=rng.randint(0,30)))
    exchanges = [
        (buyer,  "Hi, is this still available?"),
        (seller, "Yes, still available! What would you like to know?"),
        (buyer,  "Does it fit my car exactly? Any issues I should know about?"),
        (seller, "Came off a well-maintained car. No issues at all."),
        (buyer,  "Great — I'll add it to my cart now."),
    ]
    for sender, body in picks(exchanges, rng.randint(1, len(exchanges))):
        Message.objects.create(thread=thread, sender=sender, body=body, is_read=pct(0.5))

# ── 9. bundles ────────────────────────────────────────────────────────────────

print("Creating bundles…")
lighting_cat = BundleCategory.objects.create(name="Complete Lighting Kit", type="assembly")
discount_cat  = BundleCategory.objects.create(name="Value Pack",            type="discount")

for vehicle in picks(all_vehicles, min(5, len(all_vehicles))):
    vehicle_items = list(Item.objects.filter(vehicle=vehicle, status="active"))
    if len(vehicle_items) < 2:
        continue
    bundle = Bundle.objects.create(
        bundle_category=pick([lighting_cat, discount_cat]),
        name=f"{vehicle.year} {vehicle.generation.car_model.name if vehicle.generation else 'Parts'} Bundle",
        discount_pct=round(rng.uniform(5, 20), 1),
        status="active",
    )
    for item in picks(vehicle_items, min(3, len(vehicle_items))):
        BundleItem.objects.get_or_create(bundle=bundle, item=item)

# ── 10. variations ────────────────────────────────────────────────────────────

print("Creating variations…")
for item in picks(all_items, min(15, len(all_items))):
    Variation.objects.create(
        vehicle=item.vehicle, item=item,
        item_snapshot={"title": item.title, "price": str(item.price),
                       "condition": item.condition, "category": item.category.slug},
        ai_confidence=pick(["high","high","medium","low"]),
        review_status=pick(["approved","approved","pending","rejected"]),
    )

# ─── summary ──────────────────────────────────────────────────────────────────

print("\n✓ Seed complete!")
print(f"  Makes:          {Make.objects.count()}")
print(f"  Car models:     {CarModel.objects.count()}")
print(f"  Generations:    {Generation.objects.count()}")
print(f"  Modifications:  {Modification.objects.count()}")
print(f"  Categories:     {Category.objects.count()}")
print(f"  Option cats:    {OptionCategory.objects.count()}")
print(f"  Option values:  {OptionValue.objects.count()}")
print(f"  Users:          {User.objects.count()} (admin + {len(sellers)} sellers + {len(buyers)} buyers)")
print(f"  Vehicles:       {Vehicle.objects.count()}")
print(f"  Items:          {Item.objects.count()}")
print(f"  Options:        {Option.objects.count()}")
print(f"  Part numbers:   {PartNumber.objects.count()}")
print(f"  Compatibilities:{ItemCompatibility.objects.count()}")
print(f"  Orders:         {Order.objects.count()}")
print(f"  Reviews:        {SellerReview.objects.count()}")
print(f"  Disputes:       {Dispute.objects.count()}")
print(f"  Threads:        {Thread.objects.count()}")
print(f"  Bundles:        {Bundle.objects.count()}")
print()
print("Login credentials:")
print("  admin@partbridge.com / admin1234")
print("  seller1@example.com  / password123  (is_seller=True)")
print("  buyer1@example.com   / password123")
