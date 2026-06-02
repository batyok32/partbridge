from datetime import timedelta
from unittest.mock import AsyncMock, patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.test import APIClient

from vehicles.models import PartFamily, Vehicle, VehiclePart
from vehicles.serializers import VehiclePartSerializer

User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CELERY_TASK_ALWAYS_EAGER=True,
    SCRAPING_BEE_API_KEY="test-key",
    DEEPSEEK_API_KEY="test-key",
    OPENAI_API_KEY="test-key",
)
class VehicleApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="seller@example.com",
            password="pw-test-12",
            name="Seller",
            phone="+12065550101",
        )
        self.user.email_verified_at = timezone.now()
        self.user.role = User.Role.BOTH
        self.user.save(update_fields=["email_verified_at", "role"])
        self.client.force_authenticate(user=self.user)
        mail.outbox.clear()

    def test_decode_vin_endpoint(self):
        fake = {
            "vin": "1HGBH41JXMN109186",
            "suggested": {
                "year": 2015,
                "make": "HONDA",
                "model": "Civic",
                "trim": "LX",
                "engine": "1.8L Gasoline",
                "transmission": "",
                "drivetrain": "FWD",
                "body_style": "Sedan",
                "color": "",
            },
            "nhtsa_error_code": "0",
            "nhtsa_error_text": None,
            "nhtsa_warning": False,
        }
        with patch("vehicles.views.decode_vin", return_value=fake):
            r = self.client.post("/api/v1/vin/decode/", {"vin": "1HGBH41JXMN109186"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()["suggested"]["make"], "HONDA")

    def test_create_vehicle_starts_processing_then_ready(self):
        fake_report = {
            "scraped_at": "2026-01-01T00:00:00+00:00",
            "part_out_summary": {"estimated_total_net": 12500},
            "stats": {"combined": {"count": 12, "median_price": 45.0}},
            "counts": {"kept": {"total": 12}},
            "top_opportunities": [],
        }
        scraper_inst = AsyncMock()
        scraper_inst.scrape = AsyncMock(return_value=fake_report)
        with patch(
            "analytics.services.bee_ai_scraper.ScrapingBeeAIScraper",
            return_value=scraper_inst,
        ):
            with self.captureOnCommitCallbacks(execute=True):
                r = self.client.post(
                    "/api/v1/vehicles/",
                    {
                        "vin": "1HGBH41JXMN109186",
                        "year": 2015,
                        "make": "Honda",
                        "model": "Civic",
                        "location_state": "WA",
                        "location_zip": "98101",
                    },
                    format="json",
                )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.content)
        self.assertEqual(r.json().get("analytics_status"), Vehicle.AnalyticsStatus.PROCESSING)
        vid = r.json()["id"]
        v = Vehicle.objects.get(pk=vid)
        self.assertEqual(v.analytics_status, Vehicle.AnalyticsStatus.READY)
        self.assertIsNotNone(v.analytics_last_completed_at)
        self.assertIsNotNone(v.analytics_next_refresh_at)
        self.assertEqual(len(mail.outbox), 1)

        r2 = self.client.post(f"/api/v1/vehicles/{vid}/seed_parts/")
        self.assertEqual(r2.status_code, status.HTTP_200_OK, r2.content)

    def test_seed_skips_buy_new_only(self):
        belt = PartFamily.objects.get(slug="serpentine_belt")
        self.assertTrue(belt.buy_new_only)
        v = Vehicle.objects.create(
            owner=self.user,
            vin="2HGFG12659H123456",
            year=2010,
            make="Honda",
            model="Fit",
        )
        from vehicles.catalog_seed import seed_parts_for_vehicle

        seed_parts_for_vehicle(v)
        self.assertFalse(VehiclePart.objects.filter(part_family=belt).exists())

    def test_patch_part_and_infer_damage(self):
        v = Vehicle.objects.create(
            owner=self.user,
            vin="3VWDX7AJ5DM123456",
            year=2013,
            make="VW",
            model="Jetta",
        )
        self.client.post(f"/api/v1/vehicles/{v.id}/seed_parts/")
        part = VehiclePart.objects.filter(vehicle=v, is_removed=False).order_by("id").first()
        r = self.client.patch(
            f"/api/v1/vehicles/{v.id}/parts/{part.id}/",
            {"listing_state": "draft", "description": "Test note"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        part.refresh_from_db()
        self.assertEqual(part.listing_state, "draft")

        r2 = self.client.post(
            f"/api/v1/vehicles/{v.id}/infer_damage/",
            {"damage_notes": ["major front end collision"]},
            format="json",
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(r2.json()["marked"], 0)

    def test_buy_now_requires_price_and_condition(self):
        v = Vehicle.objects.create(
            owner=self.user,
            vin="4T1BE46K37U042000",
            year=2007,
            make="Toyota",
            model="Camry",
        )
        self.client.post(f"/api/v1/vehicles/{v.id}/seed_parts/")
        part = VehiclePart.objects.filter(vehicle=v).first()
        r = self.client.patch(
            f"/api/v1/vehicles/{v.id}/parts/{part.id}/",
            {"listing_state": "buy_now"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        r2 = self.client.patch(
            f"/api/v1/vehicles/{v.id}/parts/{part.id}/",
            {
                "listing_state": "buy_now",
                "price": "89.00",
                "condition_draft": "oem_tested",
            },
            format="json",
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK, r2.content)
        part.refresh_from_db()
        self.assertEqual(part.listing_state, VehiclePart.ListingState.BUY_NOW)
        self.assertIsNone(part.buy_now_expires_at)
        self.assertEqual(r2.json().get("listing_state_effective"), "buy_now")

    def test_buy_now_validate_rejects_missing_price_on_create_shaped_payload(self):
        ser = VehiclePartSerializer()
        ser.instance = None
        with self.assertRaises(serializers.ValidationError) as ctx:
            ser.validate(
                {
                    "listing_state": VehiclePart.ListingState.BUY_NOW,
                    "price": None,
                    "condition_draft": VehiclePart.ConditionDraft.USED,
                }
            )
        self.assertIn("price", ctx.exception.detail)

    def test_apply_price_template_skips_zero_price_line(self):
        v = Vehicle.objects.create(
            owner=self.user,
            vin="JM1BK32F581234567",
            year=2008,
            make="Mazda",
            model="3",
        )
        pf = PartFamily.objects.filter(buy_new_only=False).first()
        self.assertIsNotNone(pf)
        r = self.client.post(
            f"/api/v1/vehicles/{v.id}/apply_price_template/",
            {"template_text": f"{pf.name} $0.00", "condition_draft": "used"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        data = r.json()
        self.assertGreaterEqual(data.get("skipped", 0), 1)
        reasons = " ".join((row.get("reason") or "") for row in data.get("results", [])).lower()
        self.assertIn("zero", reasons)

    def test_expire_buy_now_listings_task(self):
        from vehicles.tasks import expire_buy_now_listings

        v = Vehicle.objects.create(
            owner=self.user,
            vin="5YFBURHE0FP123456",
            year=2015,
            make="Toyota",
            model="Corolla",
        )
        self.client.post(f"/api/v1/vehicles/{v.id}/seed_parts/")
        part = VehiclePart.objects.filter(vehicle=v).first()
        part.listing_state = VehiclePart.ListingState.BUY_NOW
        part.price = 50
        part.condition_draft = "used"
        part.buy_now_expires_at = timezone.now() - timedelta(hours=1)
        part.save()
        expire_buy_now_listings()
        part.refresh_from_db()
        self.assertEqual(part.listing_state, VehiclePart.ListingState.DRAFT)
        self.assertIsNone(part.buy_now_expires_at)

    def test_catalog_categories(self):
        r = self.client.get("/api/v1/catalog/part-categories/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertGreater(len(r.json()), 5)


class PublicBrowseTests(TestCase):
    """Phase 5 — anonymous discovery."""

    @override_settings(PERPLEXITY_API_KEY="")
    def test_suggest_cars_fallback_emits_inclusive_year_range(self):
        from vehicles.ai_assist import normalize_candidate_vehicle, suggest_cars_and_part_phrase

        out = suggest_cars_and_part_phrase(
            buyer_year=2015,
            buyer_make="Toyota",
            buyer_model="Corolla",
            part_query="headlight",
        )
        self.assertEqual(out["source"], "fallback")
        self.assertEqual(len(out["candidate_vehicles"]), 1)
        c = out["candidate_vehicles"][0]
        self.assertEqual(c["year_range_start"], 2013)
        self.assertEqual(c["year_range_end"], 2017)
        self.assertEqual(c["make"], "Toyota")
        self.assertEqual(c["model"], "Corolla")

        legacy = normalize_candidate_vehicle(
            {"year": 2012, "make": "Ford", "model": "F-150", "trim": "", "reason": "legacy row"}
        )
        self.assertIsNotNone(legacy)
        self.assertEqual(legacy["year_range_start"], 2012)
        self.assertEqual(legacy["year_range_end"], 2012)

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="public@example.com",
            password="pw-test-12",
            name="Seller",
            phone="+12065550101",
        )
        self.user.email_verified_at = timezone.now()
        self.user.role = User.Role.BOTH
        self.user.save(update_fields=["email_verified_at", "role"])

    def test_anonymous_browse_lists_message_only_parts(self):
        v = Vehicle.objects.create(
            owner=self.user,
            vin="1HGBH41JXMN109186",
            year=2015,
            make="Honda",
            model="Civic",
            location_state="WA",
            location_zip="98101",
        )
        self.client.force_authenticate(user=self.user)
        self.client.post(f"/api/v1/vehicles/{v.id}/seed_parts/")
        self.client.force_authenticate(user=None)
        part = VehiclePart.objects.filter(vehicle=v).first()
        part.listing_state = VehiclePart.ListingState.MESSAGE_ONLY
        part.save()
        r = self.client.get("/api/v1/browse/parts/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        data = r.json()
        self.assertGreaterEqual(data["count"], 1)
        row = next(
            (
                x
                for x in data["results"]
                if (x.get("vehicle_public") or {}).get("year") == 2015
                and (x.get("vehicle_public") or {}).get("model") == "Civic"
            ),
            None,
        )
        self.assertIsNotNone(row)
        self.assertIn("vehicle_public", row)
        self.assertNotIn("vin", str(row))

    def test_draft_in_public_browse_for_discovery(self):
        v = Vehicle.objects.create(
            owner=self.user,
            vin="2HGFG12659H123456",
            year=2010,
            make="Honda",
            model="Fit",
            location_state="WA",
            location_zip="98102",
        )
        self.client.force_authenticate(user=self.user)
        self.client.post(f"/api/v1/vehicles/{v.id}/seed_parts/")
        self.client.force_authenticate(user=None)
        part = VehiclePart.objects.filter(vehicle=v, is_removed=False).order_by("id").first()
        self.assertEqual(part.listing_state, VehiclePart.ListingState.DRAFT)
        r = self.client.get("/api/v1/browse/parts/?year=2010&make=Honda&model=Fit")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        row = next(
            (
                x
                for x in r.json()["results"]
                if (x.get("vehicle_public") or {}).get("year") == 2010
                and (x.get("vehicle_public") or {}).get("model") == "Fit"
            ),
            None,
        )
        self.assertIsNotNone(row)

    def test_catalog_categories_anonymous(self):
        self.client.force_authenticate(user=None)
        r = self.client.get("/api/v1/catalog/part-categories/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertGreater(len(r.json()), 5)

    def test_browse_car_options_endpoint(self):
        v = Vehicle.objects.create(
            owner=self.user,
            vin="6YFBURHE0FP123456",
            year=2016,
            make="Toyota",
            model="Corolla",
        )
        self.client.force_authenticate(user=self.user)
        self.client.post(f"/api/v1/vehicles/{v.id}/seed_parts/")
        self.client.force_authenticate(user=None)
        r = self.client.get("/api/v1/browse/cars/options/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("years", r.json())

    def test_car_assist_endpoint_returns_listings_and_car_buckets(self):
        v = Vehicle.objects.create(
            owner=self.user,
            vin="5YFBURHE0FP123456",
            year=2015,
            make="Toyota",
            model="Corolla",
            location_state="WA",
            location_zip="98103",
        )
        self.client.force_authenticate(user=self.user)
        self.client.post(f"/api/v1/vehicles/{v.id}/seed_parts/")
        part = VehiclePart.objects.filter(vehicle=v, is_removed=False).order_by("id").first()
        part.listing_state = VehiclePart.ListingState.MESSAGE_ONLY
        part.label = "Left Headlight Assembly"
        part.save(update_fields=["listing_state", "label"])
        self.client.force_authenticate(user=None)

        r = self.client.post(
            "/api/v1/browse/cars/assist/",
            {
                "buyer_year": 2014,
                "buyer_make": "Toyota",
                "buyer_model": "Corolla",
                "part_need": "left headlight",
                "buyer_zip": "98101",
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        data = r.json()
        self.assertIn("listings", data)
        self.assertGreaterEqual(len(data["listings"]), 1)
        self.assertIn("listings_total_count", data)
        self.assertGreaterEqual(
            data["listings_total_count"],
            len(data["listings"]),
            "total count should cover all serialized rows",
        )
        self.assertIn("potential_cars", data)
        self.assertEqual(data.get("search_mode"), "custom_part")
        self.assertIn("part_refinement", data)

    def test_car_assist_shows_donor_cars_by_ymm_when_no_part_match(self):
        """Potential donors use Y/M/M only — not whether the part query matched a listing."""
        v = Vehicle.objects.create(
            owner=self.user,
            vin="7YFBURHE0FP123456",
            year=2015,
            make="Toyota",
            model="Corolla",
            location_state="WA",
            location_zip="98103",
        )
        self.client.force_authenticate(user=self.user)
        self.client.post(f"/api/v1/vehicles/{v.id}/seed_parts/")
        part = VehiclePart.objects.filter(vehicle=v, is_removed=False).order_by("id").first()
        part.listing_state = VehiclePart.ListingState.MESSAGE_ONLY
        part.label = "Left Headlight Assembly"
        part.save(update_fields=["listing_state", "label"])
        self.client.force_authenticate(user=None)

        fake_refine = {
            "refined_query": "zzzz_no_inventory_match_zzzz",
            "note": "",
            "source": "test",
        }
        fake_suggest = {
            "normalized_part_query": "zzzz_no_inventory_match_zzzz",
            "candidate_vehicles": [],
            "source": "test",
        }
        with patch("vehicles.views.deepseek_refine_part_phrase", return_value=fake_refine):
            with patch("vehicles.views.suggest_cars_and_part_phrase", return_value=fake_suggest):
                r = self.client.post(
                    "/api/v1/browse/cars/assist/",
                    {
                        "buyer_year": 2015,
                        "buyer_make": "Toyota",
                        "buyer_model": "Corolla",
                        "part_need": "something not in any label",
                        "buyer_zip": "98101",
                    },
                    format="json",
                )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        data = r.json()
        self.assertEqual(len(data.get("listings") or []), 0)
        cars = data.get("potential_cars") or []
        self.assertGreaterEqual(len(cars), 1)
        self.assertTrue(any(c.get("vehicle_id") == v.id for c in cars))

    def test_car_assist_cars_only_matches_make_model_any_year(self):
        """Browse with no part: all listable parts for make/model, any model year (year not a filter)."""
        vins = ("1HGBH41JXMN109186", "1HGBH41JXMN209186")
        self.client.force_authenticate(user=self.user)
        for i, yr in enumerate((2010, 2015)):
            v = Vehicle.objects.create(
                owner=self.user,
                vin=vins[i],
                year=yr,
                make="Honda",
                model="Fit",
            )
            self.client.post(f"/api/v1/vehicles/{v.id}/seed_parts/")
            p = VehiclePart.objects.filter(vehicle=v, is_removed=False).order_by("id").first()
            p.listing_state = VehiclePart.ListingState.MESSAGE_ONLY
            p.save(update_fields=["listing_state"])
        self.client.force_authenticate(user=None)

        r = self.client.post(
            "/api/v1/browse/cars/assist/",
            {
                "buyer_year": 2015,
                "buyer_make": "Honda",
                "buyer_model": "Fit",
                "category": "",
                "part_need": "",
                "buyer_zip": "",
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        data = r.json()
        self.assertEqual(data.get("search_mode"), "cars_only")
        listings = data.get("listings") or []
        self.assertGreaterEqual(len(listings), 1)
        # Part rows are capped and sorted by updated_at — both donor years still appear as vehicles.
        pot_years = {c.get("year") for c in (data.get("potential_cars") or [])}
        self.assertIn(2010, pot_years)
        self.assertIn(2015, pot_years)

    def test_car_assist_requires_make_model_or_part(self):
        r = self.client.post(
            "/api/v1/browse/cars/assist/",
            {"buyer_zip": "98101", "category": "", "part_need": ""},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST, r.content)

    def test_car_assist_rejects_category_and_part_together(self):
        r = self.client.post(
            "/api/v1/browse/cars/assist/",
            {
                "part_need": "headlight",
                "category": "body_exterior",
                "buyer_zip": "98101",
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST, r.content)

    def test_public_browse_vehicle_detail(self):
        v = Vehicle.objects.create(
            owner=self.user,
            vin="1HGBH41JXMN109186",
            year=2015,
            make="Honda",
            model="Fit",
            location_state="WA",
            location_zip="98101",
        )
        self.client.force_authenticate(user=self.user)
        self.client.post(f"/api/v1/vehicles/{v.id}/seed_parts/")
        part = VehiclePart.objects.filter(vehicle=v, is_removed=False).order_by("id").first()
        part.listing_state = VehiclePart.ListingState.MESSAGE_ONLY
        part.save(update_fields=["listing_state"])
        self.client.force_authenticate(user=None)

        r = self.client.get(f"/api/v1/browse/vehicles/{v.id}/")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        data = r.json()
        self.assertEqual(data["vehicle"]["id"], v.id)
        self.assertIn("parts", data)
        self.assertGreaterEqual(data["parts_count"], 1)
        self.assertIsInstance(data["parts"], list)
        self.assertEqual(data.get("parts_page"), 1)
        self.assertGreaterEqual(data.get("parts_total_pages", 0), 1)
        self.assertEqual(data.get("parts_page_size"), 120)

    def test_public_browse_vehicle_detail_buy_now_only_and_search(self):
        v = Vehicle.objects.create(
            owner=self.user,
            vin="3HGBH41JXMN109186",
            year=2016,
            make="Honda",
            model="Accord",
            location_state="WA",
            location_zip="98101",
        )
        self.client.force_authenticate(user=self.user)
        self.client.post(f"/api/v1/vehicles/{v.id}/seed_parts/")
        bn = VehiclePart.objects.filter(vehicle=v, is_removed=False).order_by("id").first()
        self.assertIsNotNone(bn)
        bn.listing_state = VehiclePart.ListingState.BUY_NOW
        bn.price = 42
        bn.condition_draft = VehiclePart.ConditionDraft.USED
        bn.label = "XYZZY_PB_TEST_99283_HEADLAMP"
        bn.save(update_fields=["listing_state", "price", "condition_draft", "label"])
        self.client.force_authenticate(user=None)

        r = self.client.get(f"/api/v1/browse/vehicles/{v.id}/?buy_now_only=1")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        data = r.json()
        self.assertIn("other_parts", data)
        self.assertGreaterEqual(data["parts_count"], 1)
        ids = {p["id"] for p in data["parts"]}
        self.assertIn(bn.id, ids)

        r2 = self.client.get(f"/api/v1/browse/vehicles/{v.id}/?buy_now_only=1&q=XYZZY_PB_TEST_99283")
        self.assertEqual(r2.status_code, status.HTTP_200_OK, r2.content)
        d2 = r2.json()
        self.assertEqual(d2["parts_count"], 1)
        self.assertEqual(len(d2["parts"]), 1)
        self.assertEqual(d2["parts"][0]["id"], bn.id)

    def test_public_browse_vehicle_detail_404_without_listable_parts(self):
        v = Vehicle.objects.create(
            owner=self.user,
            vin="2HGBH41JXMN109186",
            year=2014,
            make="Honda",
            model="Civic",
        )
        self.client.force_authenticate(user=None)
        r = self.client.get(f"/api/v1/browse/vehicles/{v.id}/")
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)
