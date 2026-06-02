from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from orders.models import Order
from orders.tasks import auto_cancel_unconfirmed_paid_orders, enforce_first_sale_verification_deadline
from vehicles.models import Vehicle, VehiclePart

User = get_user_model()


@override_settings(STRIPE_SECRET_KEY="", STRIPE_WEBHOOK_SECRET="")
class OrderApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.buyer = User.objects.create_user(
            email="buyer-phase7@example.com",
            password="pw-test-12",
            name="Buyer",
            phone="+12065550199",
            role="buyer",
        )
        self.seller = User.objects.create_user(
            email="seller-phase7@example.com",
            password="pw-test-12",
            name="Seller",
            phone="+12065550101",
            role="seller",
        )
        self.buyer.email_verified_at = timezone.now()
        self.seller.email_verified_at = timezone.now()
        self.buyer.save(update_fields=["email_verified_at"])
        self.seller.save(update_fields=["email_verified_at"])

        vehicle = Vehicle.objects.create(
            owner=self.seller,
            vin="1HGBH41JXMN109186",
            year=2015,
            make="Honda",
            model="Civic",
            location_state="WA",
            location_zip="98101",
        )
        self.client.force_authenticate(user=self.seller)
        self.client.post(f"/api/v1/vehicles/{vehicle.id}/seed_parts/")
        self.part = VehiclePart.objects.filter(vehicle=vehicle, is_removed=False).first()
        self.part.listing_state = VehiclePart.ListingState.BUY_NOW
        self.part.price = "120.00"
        self.part.condition_draft = "used"
        self.part.save(update_fields=["listing_state", "price", "condition_draft", "updated_at"])
        self.client.force_authenticate(user=None)

    def test_checkout_intent_requires_mandatory_checks(self):
        self.client.force_authenticate(user=self.buyer)
        r = self.client.post(
            "/api/v1/orders/checkout-intent/",
            {
                "vehicle_part_id": self.part.id,
                "fitment_verified": False,
                "return_policy_read": True,
            },
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_checkout_then_confirm_payment_sets_escrow(self):
        self.client.force_authenticate(user=self.buyer)
        r = self.client.post(
            "/api/v1/orders/checkout-intent/",
            {
                "vehicle_part_id": self.part.id,
                "fitment_verified": True,
                "return_policy_read": True,
                "shipping_mode": "pickup",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        order_id = r.json()["id"]
        self.assertEqual(r.json()["state"], Order.State.PAYMENT_PENDING)

        r2 = self.client.post(
            f"/api/v1/orders/{order_id}/confirm-payment/",
            {"status": "succeeded"},
            format="json",
        )
        self.assertEqual(r2.status_code, 200, r2.content)
        order = Order.objects.get(pk=order_id)
        self.assertEqual(order.state, Order.State.SELLER_CONFIRMED)
        self.part.refresh_from_db()
        self.assertEqual(self.part.listing_state, VehiclePart.ListingState.SOLD)

    def test_five_day_rule_keeps_order_but_blocks_cashout(self):
        self.client.force_authenticate(user=self.buyer)
        r = self.client.post(
            "/api/v1/orders/checkout-intent/",
            {
                "vehicle_part_id": self.part.id,
                "fitment_verified": True,
                "return_policy_read": True,
                "shipping_mode": "pickup",
            },
            format="json",
        )
        order_id = r.json()["id"]
        self.client.post(
            f"/api/v1/orders/{order_id}/confirm-payment/",
            {"status": "succeeded"},
            format="json",
        )
        order = Order.objects.get(pk=order_id)
        order.payout_block_deadline = timezone.now() - timedelta(minutes=1)
        order.save(update_fields=["payout_block_deadline"])

        result = enforce_first_sale_verification_deadline()
        order.refresh_from_db()
        self.assertEqual(order.state, Order.State.SELLER_CONFIRMED)
        self.assertIn("Cashout blocked", order.payout_block_reason)
        self.assertGreaterEqual(result["overdue_payout_blocks"], 1)

    def test_seller_confirm_pre_ship_and_label_purchase(self):
        self.client.force_authenticate(user=self.buyer)
        r = self.client.post(
            "/api/v1/orders/checkout-intent/",
            {
                "vehicle_part_id": self.part.id,
                "fitment_verified": True,
                "return_policy_read": True,
                "shipping_mode": "pickup",
            },
            format="json",
        )
        order_id = r.json()["id"]
        self.client.post(
            f"/api/v1/orders/{order_id}/confirm-payment/",
            {"status": "succeeded"},
            format="json",
        )

        self.client.force_authenticate(user=self.seller)

        r_pre = self.client.post(
            f"/api/v1/orders/{order_id}/pre-ship/",
            {
                "pre_ship_photos": [
                    "https://example.com/1.jpg",
                    "https://example.com/2.jpg",
                    "https://example.com/3.jpg",
                    "https://example.com/4.jpg",
                ],
                "package_length_in": "20.00",
                "package_width_in": "14.00",
                "package_height_in": "8.00",
                "package_weight_lb": "15.00",
                "overage_acknowledged": True,
                "insurance_opt_in": True,
                "pickup_days": 2,
            },
            format="json",
        )
        self.assertEqual(r_pre.status_code, 200, r_pre.content)

        r_label = self.client.post(
            f"/api/v1/orders/{order_id}/purchase-label/",
            {"carrier": "ups"},
            format="json",
        )
        self.assertEqual(r_label.status_code, 200, r_label.content)
        order = Order.objects.get(pk=order_id)
        self.assertEqual(order.state, Order.State.LABEL_PURCHASED)
        self.assertTrue(order.shipping_label_url)
        self.assertTrue(order.tracking_number)

    def test_tracking_webhook_marks_delivered(self):
        self.client.force_authenticate(user=self.buyer)
        r = self.client.post(
            "/api/v1/orders/checkout-intent/",
            {
                "vehicle_part_id": self.part.id,
                "fitment_verified": True,
                "return_policy_read": True,
                "shipping_mode": "pickup",
            },
            format="json",
        )
        order_id = r.json()["id"]
        self.client.post(
            f"/api/v1/orders/{order_id}/confirm-payment/",
            {"status": "succeeded"},
            format="json",
        )
        self.client.force_authenticate(user=self.seller)
        self.client.post(
            f"/api/v1/orders/{order_id}/pre-ship/",
            {
                "pre_ship_photos": [
                    "https://example.com/1.jpg",
                    "https://example.com/2.jpg",
                    "https://example.com/3.jpg",
                    "https://example.com/4.jpg",
                ],
                "package_length_in": "20.00",
                "package_width_in": "14.00",
                "package_height_in": "8.00",
                "package_weight_lb": "15.00",
                "overage_acknowledged": True,
                "insurance_opt_in": False,
                "pickup_days": 1,
            },
            format="json",
        )
        self.client.post(f"/api/v1/orders/{order_id}/purchase-label/", {"carrier": "usps"}, format="json")
        order = Order.objects.get(pk=order_id)
        self.client.force_authenticate(user=None)
        r_track = self.client.post(
            "/api/v1/orders/tracking/webhook/",
            {
                "order_id": order_id,
                "tracking_number": order.tracking_number,
                "carrier": "usps",
                "status": "delivered",
            },
            format="json",
        )
        self.assertEqual(r_track.status_code, 200, r_track.content)
        order.refresh_from_db()
        self.assertEqual(order.state, Order.State.DELIVERED)

    def test_auto_cancel_unconfirmed_after_24h(self):
        self.client.force_authenticate(user=self.buyer)
        r = self.client.post(
            "/api/v1/orders/checkout-intent/",
            {
                "vehicle_part_id": self.part.id,
                "fitment_verified": True,
                "return_policy_read": True,
                "shipping_mode": "pickup",
            },
            format="json",
        )
        order_id = r.json()["id"]
        self.client.post(
            f"/api/v1/orders/{order_id}/confirm-payment/",
            {"status": "succeeded"},
            format="json",
        )
        order = Order.objects.get(pk=order_id)
        order.state = Order.State.PAID_ESCROW
        order.seller_confirmed_at = None
        order.seller_confirmation_due_at = timezone.now() - timedelta(minutes=1)
        order.save(update_fields=["state", "seller_confirmed_at", "seller_confirmation_due_at"])
        out = auto_cancel_unconfirmed_paid_orders()
        order.refresh_from_db()
        self.assertEqual(order.state, Order.State.REFUNDED)
        self.part.refresh_from_db()
        self.assertEqual(self.part.listing_state, VehiclePart.ListingState.UNAVAILABLE)
        self.assertGreaterEqual(out["auto_cancelled_orders"], 1)

    def test_cart_add_and_checkout(self):
        self.client.force_authenticate(user=self.buyer)
        r_add = self.client.post(
            "/api/v1/cart/",
            {"vehicle_part_id": self.part.id, "quantity": 1, "shipping_mode": "pickup"},
            format="json",
        )
        self.assertIn(r_add.status_code, (200, 201), r_add.content)
        r_checkout = self.client.post("/api/v1/cart/checkout/", {}, format="json")
        self.assertEqual(r_checkout.status_code, 201, r_checkout.content)
        self.assertGreaterEqual(r_checkout.json()["orders_created"], 1)
        r_cart_after = self.client.get("/api/v1/cart/")
        self.assertGreaterEqual(len(r_cart_after.json()), 1, "Cart should stay until payment succeeds.")
        order_id = r_checkout.json()["orders"][0]["id"]
        r_pay = self.client.post(
            f"/api/v1/orders/{order_id}/confirm-payment/",
            {"status": "succeeded"},
            format="json",
        )
        self.assertEqual(r_pay.status_code, 200, r_pay.content)
        r_cart_empty = self.client.get("/api/v1/cart/")
        self.assertEqual(len(r_cart_empty.json()), 0)

    def test_money_summary_endpoint(self):
        self.client.force_authenticate(user=self.seller)
        r = self.client.get("/api/v1/orders/money/summary/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn("balance", r.json())
