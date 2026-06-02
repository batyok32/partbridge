from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from messaging.models import Quote, Thread
from vehicles.models import Vehicle, VehiclePart

User = get_user_model()


class MessagingApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.buyer = User.objects.create_user(
            email="buyer@example.com",
            password="pw-test-12",
            name="Buyer",
            phone="+12065550101",
            role="buyer",
        )
        self.seller = User.objects.create_user(
            email="seller@example.com",
            password="pw-test-12",
            name="Seller",
            phone="+12065550102",
            role="seller",
        )
        self.buyer.email_verified_at = timezone.now()
        self.seller.email_verified_at = timezone.now()
        self.buyer.save(update_fields=["email_verified_at"])
        self.seller.save(update_fields=["email_verified_at"])

        self.vehicle = Vehicle.objects.create(
            owner=self.seller,
            vin="1HGBH41JXMN109186",
            year=2015,
            make="Honda",
            model="Civic",
        )
        self.client.force_authenticate(user=self.seller)
        self.client.post(f"/api/v1/vehicles/{self.vehicle.id}/seed_parts/")
        self.part = VehiclePart.objects.filter(vehicle=self.vehicle).first()
        self.part.listing_state = VehiclePart.ListingState.MESSAGE_ONLY
        self.part.save(update_fields=["listing_state"])
        self.client.force_authenticate(user=None)

    def test_buyer_can_start_thread_and_send_message(self):
        self.client.force_authenticate(user=self.buyer)
        r = self.client.post(
            "/api/v1/messages/start/",
            {"vehicle_part_id": self.part.id, "message": "Is this still available?"},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        data = r.json()
        self.assertEqual(data["vehicle_part_id"], self.part.id)
        self.assertEqual(len(data["messages"]), 1)
        self.assertEqual(Thread.objects.count(), 1)

    def test_bulk_rfq_creates_multiple_threads(self):
        second_vehicle = Vehicle.objects.create(
            owner=self.seller,
            vin="2HGFG12659H123456",
            year=2012,
            make="Honda",
            model="Fit",
        )
        self.client.force_authenticate(user=self.seller)
        self.client.post(f"/api/v1/vehicles/{second_vehicle.id}/seed_parts/")
        second_part = VehiclePart.objects.filter(vehicle=second_vehicle).first()
        second_part.listing_state = VehiclePart.ListingState.MESSAGE_ONLY
        second_part.save(update_fields=["listing_state"])

        other_seller = User.objects.create_user(
            email="seller2@example.com",
            password="pw-test-12",
            name="Seller 2",
            phone="+12065550103",
            role="seller",
        )
        other_seller.email_verified_at = timezone.now()
        other_seller.save(update_fields=["email_verified_at"])
        v3 = Vehicle.objects.create(
            owner=other_seller,
            vin="3VWDX7AJ5DM123456",
            year=2013,
            make="VW",
            model="Jetta",
        )
        self.client.force_authenticate(user=other_seller)
        self.client.post(f"/api/v1/vehicles/{v3.id}/seed_parts/")
        third_part = VehiclePart.objects.filter(vehicle=v3).first()
        third_part.listing_state = VehiclePart.ListingState.MESSAGE_ONLY
        third_part.save(update_fields=["listing_state"])

        self.client.force_authenticate(user=self.buyer)
        r = self.client.post(
            "/api/v1/messages/bulk-rfq/",
            {
                "vehicle_part_ids": [self.part.id, second_part.id, third_part.id],
                "message": "Looking for best shipped price to 98101.",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["threads_created"], 3)

    def test_only_seller_can_send_quote(self):
        self.part.listing_state = VehiclePart.ListingState.BUY_NOW
        self.part.price = "100.00"
        self.part.condition_draft = "used"
        self.part.save(update_fields=["listing_state", "price", "condition_draft", "updated_at"])
        self.client.force_authenticate(user=self.buyer)
        thread_resp = self.client.post(
            "/api/v1/messages/start/",
            {"vehicle_part_id": self.part.id, "message": "Quote please."},
            format="json",
        )
        thread_id = thread_resp.json()["id"]

        r_buyer = self.client.post(
            f"/api/v1/messages/threads/{thread_id}/quote/",
            {"price": "120.00", "note": "Can ship tomorrow"},
            format="json",
        )
        self.assertEqual(r_buyer.status_code, 403)

        self.client.force_authenticate(user=self.seller)
        r_seller = self.client.post(
            f"/api/v1/messages/threads/{thread_id}/quote/",
            {"price": "120.00", "note": "Can ship tomorrow"},
            format="json",
        )
        self.assertEqual(r_seller.status_code, 201, r_seller.content)
        self.assertEqual(Quote.objects.filter(thread_id=thread_id).count(), 1)
