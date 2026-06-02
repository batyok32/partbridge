# Django `views.py` reference

Detailed reference for every **`APIView`**, **generic view**, **ViewSet**, and important **module-level helpers** in each app’s `views.py`. URLs are under **`/api/v1/`** unless noted.

---

## `backend/accounts/views.py`

Authentication, registration, email verification, JWT, password reset.

| Class / view | Method | Permission | Endpoint (see `accounts/urls.py`) | Behavior |
|--------------|--------|------------|-----------------------------------|----------|
| **`RegisterView`** | POST | AllowAny | `auth/register` | Validates `RegisterSerializer`, creates user, calls `_issue_verification` (challenge + email with code + link token). Returns 201 with message; does not return JWT by default. |
| **`VerifyEmailView`** | POST | AllowAny | `auth/verify-email` | Two paths: **signed link** (`token`) via `parse_email_verify_link_token`, or **email + code** against `EmailVerificationChallenge` (hashed code). Sets `email_verified_at`. Returns `UserSerializer` data on success. |
| **`ResendVerificationView`** | POST | AllowAny | `auth/resend-verification` | Looks up user by email; if unverified, re-issues challenge + email. Generic success message if user missing (no enumeration). |
| **`MeView`** | GET | IsAuthenticated | `auth/me` | Returns current user as `UserSerializer` (id, email, name, phone, **role**, verification, dates). |
| **`LoginView`** | POST | AllowAny | `auth/login` | Subclasses **`TokenObtainPairView`** with **`EmailVerifiedTokenObtainPairSerializer`** — JWT pair; may require verified email per serializer rules. |
| **`RefreshView`** | POST | AllowAny | `auth/token/refresh` | Standard SimpleJWT refresh. |
| **`PasswordResetRequestView`** | POST | AllowAny | `auth/password-reset` | Validates email, builds uid + Django `default_token_generator` token, emails reset URL using **`FRONTEND_BASE_URL`**. |
| **`PasswordResetConfirmView`** | POST | AllowAny | `auth/password-reset/confirm` | `PasswordResetConfirmSerializer` validates uid/token and new password; `save()` updates password. |

**Helpers**

- **`_issue_verification(user)`** — Invalidates open challenges, creates `EmailVerificationChallenge`, sends `send_verification_email` with code + link token.

---

## `backend/messaging/views.py`

Buyer–seller threads anchored on a **`VehiclePart`**. All endpoints require **IsAuthenticated** unless noted.

| Class | Method | Endpoint | Behavior |
|-------|--------|----------|----------|
| **`ThreadListView`** | GET | `messages/threads/` | Lists threads for current user via `thread_for_user_qs` (buyer or seller), `ThreadSerializer`, prefetches messages/quotes. |
| **`StartThreadView`** | POST | `messages/start/` | **`StartThreadSerializer`**: `vehicle_part_id`, optional `message`. Loads part; **`_assert_buyer`** forbids messaging own listing. **`_upsert_thread`** get_or_create by buyer+seller+part. Optionally creates first `Message`, updates read timestamps. Returns **`ThreadDetailSerializer`** 201. |
| **`BulkRfqView`** | POST | `messages/bulk-rfq/` | **`BulkRfqSerializer`**: `vehicle_part_ids` (list), `message`. For each id: loads part (skips removed), asserts buyer≠seller, upserts thread, creates message. Returns `threads_created`, `thread_ids`, `skipped`. |
| **`ThreadDetailView`** | GET | `messages/threads/<thread_id>/` | Single thread with messages and quotes, `ThreadDetailSerializer`. |
| **`ThreadMessageListCreateView`** | GET | `messages/threads/<thread_id>/messages/` | Returns `thread_id` + **messages** array only (subset of detail). |
| **`ThreadMessageListCreateView`** | POST | same | **`SendMessageSerializer`**: `body`. Creates `Message`, updates buyer/seller `last_read` and thread `updated_at`. |
| **`ThreadMarkReadView`** | POST | `messages/threads/<thread_id>/mark-read/` | **`MarkReadSerializer`**: optional `marked_at`. Updates buyer or seller read timestamp based on caller. |
| **`ThreadQuoteCreateView`** | POST | `messages/threads/<thread_id>/quote/` | **Seller only.** Part must be **Buy Now** (`effective_listing_state`). Creates **`Quote`**, optional system `Message`. Returns quote data 201. |

**Helpers**

- **`_assert_buyer(user, seller_id)`** — Raises if buyer is the listing owner.
- **`_upsert_thread(buyer, seller, vehicle_part)`** — `get_or_create` `Thread` with subject from part label.

---

## `backend/orders/views.py`

Cart, checkout, orders, seller fulfillment, money, tracking. Most classes use **IsAuthenticated**; exceptions noted.

### Payment & order creation helpers (module-level)

| Symbol | Role |
|--------|------|
| **`_ensure_seller_verification(user)`** | `get_or_create` `SellerVerification`. |
| **`_first_sale_for_seller(seller)`** | True if no order in `PAID_ESCROW` yet. |
| **`_purchase_totals_unit_price(...)`** | Computes part line + **shipping** via `shipping_preview_stub` + `shipping_amount_for_mode` for `standard` / `next_day` / `pickup`. |
| **`_create_order_intent(...)`** | Creates **`Order`** (`PAYMENT_PENDING`), Stripe **`create_payment_intent`**, stores client secret; may set **`payout_blocked`** for first-sale seller without verification. |
| **`_next_wed_or_sat`**, **`_same_state`** | Pickup scheduling heuristics for shipping-plan suggestions. |

### View classes

| Class | Methods | Endpoint | Behavior |
|-------|---------|----------|----------|
| **`CheckoutIntentView`** | POST | `orders/checkout-intent/` | Direct Buy Now checkout (not cart). Validates part is Buy Now with price, not own listing. Computes totals with shipping mode + buyer ZIP/state. **`_create_order_intent`**. Returns **`CheckoutIntentResponseSerializer`**. |
| **`ConfirmOrderPaymentView`** | POST | `orders/<order_id>/confirm-payment/` | Buyer-only, order must be `PAYMENT_PENDING`. MVP: marks payment succeeded → **`order.enter_escrow()`**, sets part **`SOLD`**, sends email/SMS to seller. |
| **`OrderListView`** | GET | `orders/` | Orders where user is **buyer or seller**; `OrderSerializer` list. |
| **`CartView`** | GET, POST | `cart/` | **GET**: user’s `CartItem`s. **POST** (`CartAddSerializer`): add/update line for Buy Now part — not own listing, ZIP required unless pickup, recomputes quoted shipping. |
| **`CartItemDetailView`** | PATCH, DELETE | `cart/<item_id>/` | **PATCH**: update shipping mode/ZIP, requote. **DELETE**: remove line. |
| **`CartCheckoutView`** | POST | `cart/checkout/` | Empties cart: for each line creates an order via **`_create_order_intent`** (atomic), then deletes all cart items. Returns list of created order payloads. |
| **`MoneySummaryView`** | GET | `orders/money/summary/` | Seller-centric aggregates: escrow totals, blocked payouts, label debits, “available” after hold; includes **`SellerVerification`** flags. |
| **`CashoutRequestView`** | POST | `orders/money/cashout/` | Requires **`payout_ready`**; otherwise 400. MVP stub success message. |
| **`QuoteAcceptCheckoutView`** | POST | `orders/quotes/<quote_id>/accept-checkout/` | Buyer accepts **`Quote`** from messaging: marks quote accepted, others rejected, **`_create_order_intent`** with `source_quote_id`. |
| **`SellerVerificationView`** | GET, POST | `orders/seller-verification/` | **GET**: verification + Stripe account id fields. **POST**: MVP toggles timestamps / `stripe_account_id` from JSON body. |
| **`SellerConfirmOrderView`** | POST | `orders/<order_id>/seller-confirm/` | Seller confirms paid order in escrow → `SELLER_CONFIRMED`, emails buyer. |
| **`SellerActionQueueView`** | GET | `orders/seller/action-queue/` | Seller dashboard queue: orders needing confirm, pickup, shipment, etc. (derived flags per order). |
| **`SellerShippingPlanSuggestView`** | POST | `orders/<order_id>/shipping-plan/suggest/` | Heuristic package dims by part label/category; suggests pickup datetime (next-day vs Wed/Sat in-state vs national). |
| **`SellerShippingPlanView`** | PATCH | `orders/<order_id>/shipping-plan/` | **`ShippingPlanSerializer`**: dimensions, weight, pickup time, insurance, overage ack — validates weekday rules for in-state vs next-day. |
| **`SellerPreShipChecklistView`** | POST | `orders/<order_id>/pre-ship/` | **`PreShipChecklistSerializer`**: photos JSON, dims, pickup window days. |
| **`SellerPurchaseLabelView`** | POST | `orders/<order_id>/purchase-label/` | MVP: synthetic label cost, tracking number, state → `LABEL_PURCHASED`, emails buyer. |
| **`TrackingWebhookView`** | POST | `orders/tracking/webhook/` | **AllowAny**. Optional header **`X-Tracking-Webhook-Secret`** vs **`TRACKING_WEBHOOK_SECRET`**. **`TrackingUpdateSerializer`** updates order tracking; may set `DELIVERED` / `SHIPPED`. |
| **`TrackingAdminOverrideView`** | POST | `orders/<order_id>/tracking/admin-override/` | **IsAdminUser**. Manual tracking status override. |

---

## `backend/analytics/views.py`

| Class | Method | Endpoint | Behavior |
|-------|--------|----------|----------|
| **`AnalyticsHealthView`** | GET | `analytics/health/` (full path: `GET /api/v1/analytics/health/`) | **IsAuthenticated**. Returns `{"status":"ok","service":"analytics"}` — wiring check. |

Market scrape results are primarily attached via **vehicle APIs** / tasks, not separate browse views (see module docstring).

---

## `backend/vehicles/views.py`

Largest module: seller vehicle CRUD, seller parts, **anonymous browse**, AI assist, utilities.

### Module-level helpers

| Function | Purpose |
|----------|---------|
| **`_vehicle_primary_photo_url`**, **`_vehicle_public_photos_payload`** | Build absolute image URLs for API responses. |
| **`_build_potential_donor_payloads(qs, ...)`** | From a `VehiclePart` queryset, aggregate top vehicles by match count → rich **`potential_cars`** cards (photos, seller stats, `sample_vehicle_part_id`). |
| **`public_listable_vehicle_parts_queryset()`** | Base queryset for **anonymous** listing discovery: not removed, sellable families, vehicle has Y/M/M, **`listing_state=BUY_NOW`** only. |
| **`public_listable_parts_for_buyer_vehicle(vd, match_year, year_slack)`** | Filter listable parts to donor vehicles matching buyer Y/M/M; optional year slack. |
| **`_vehicle_ymm_match_q`** | Q object: buyer year ± slack + make + model (legacy / tight match). |
| **`_buyer_make_model_ignore_year_q`** | Q object: make + model only. |
| **`_compat_candidates_vehicle_q(candidates)`** | OR of Perplexity-style `{make, model, year_range_*}` rows → `Q` on `vehicle__*`. |
| **`_part_search_term_q`** | OR of phrases + word tokens (≥3 chars) on label/description/part family name. |
| **`_browse_significant_tokens`** | Tokens for buy-now cross-fit description matching. |
| **`buy_now_cross_fit_parts(qs, vd, ...)`** | Buy Now parts **outside** primary compat set but with description mentioning buyer vehicle + name tokens. |

### Authenticated / seller

| Class | Role |
|-------|------|
| **`DecodeVinView`** | POST **`/vin/decode/`** — NHTSA decode via **`decode_vin`**; optional raw payload strip. |
| **`PartCategoryListView`** | GET **`catalog/part-categories/`** — list categories, **AllowAny**. |
| **`PartFamilyListView`** | GET **`catalog/part-families/`** — optional `sellable=1` filters `buy_new_only=False`. |
| **`PartsPagination`** | Page size 40, max 200 for seller part lists. |
| **`VehicleViewSet`** | CRUD **`/vehicles/`** — **owner-only**. **list**: annotated part/photo counts. **create**: sets analytics processing, **`attach_analytics_after_commit`**. **Actions**: `refresh_market_analysis`, `seed_parts`, `infer_damage`, `upload_photo` (multipart), `custom_parts` (create `PartFamily` + variants on vehicle). |
| **`VehiclePartListView`** | GET **`vehicles/<vehicle_id>/parts/`** — owner’s parts; filters `category`, `listing_state`, `hide_removed`. |
| **`VehiclePartDetailView`** | GET/PATCH/DELETE **`vehicles/<vehicle_id>/parts/<pk>/`** — **IsVehiclePartOwner**. |
| **`VehiclePhotoDeleteView`** | DELETE **`vehicles/<vehicle_id>/photos/<photo_id>/`** — removes image file + row. |

### Anonymous / public discovery

| Class | Role |
|-------|------|
| **`NormalizePartNameView`** | POST **`browse/normalize-part/`** — DeepSeek normalizes free-text part name to JSON `normalized_name`; fallback if no API key. |
| **`PublicBrowsePagination`** | page_size 24, max 48. |
| **`PublicPartBrowseView`** | GET **`browse/parts/`** — filters: year, make, model, trim, category, part_family, variant_key, `q`, damage; optional **`facets=1`** for category/variant counts. **`PublicVehiclePartSerializer`** + `buyer_zip` in context. |
| **`PublicCarAssistInputSerializer`** | (Serializer, not a view) Validates assist POST: mutual exclusivity of category vs free-text part; requires either (part or category) or (make+model). |
| **`PublicReverseZipView`** | GET **`browse/reverse-zip/?lat=&lon=`** — Nominatim reverse geocode → US ZIP. |
| **`PublicCarOptionsView`** | GET **`browse/cars/options/`** — distinct years/makes/models from DB for UI dropdowns. |
| **`PublicCarAssistView`** | POST **`browse/cars/assist/`** — **Main search** (see `HOW_IT_WORKS.md` Part B): cars-only vs part text vs category; DeepSeek + Perplexity; builds `qs`, `donor_qs`, listing union + buy-now priority + cap; **`_build_potential_donor_payloads`**. Returns listings + potential_cars + AI metadata. 500 on unexpected errors. |
| **`PublicBrowseVehicleDetailView`** | GET **`browse/vehicles/<pk>/`** — Public vehicle + up to 120 listable parts + **`inactive_parts`** (sold/unavailable). 404 if no listable parts. |
| **`PublicPartDetailView`** | GET **`browse/parts/<pk>/`** — Single **`PublicVehiclePart`** if publicly listable. |

---

## Quick lookup: URL → view

| URL prefix | File |
|------------|------|
| `auth/*` | `accounts/views.py` |
| `messages/*` | `messaging/views.py` |
| `cart/*`, `orders/*` | `orders/views.py` |
| `analytics/*` | `analytics/views.py` |
| `vin/`, `vehicles/`, `catalog/`, `browse/` | `vehicles/views.py` |

See each app’s **`urls.py`** for exact paths.

---

## Maintenance

When you add or rename a view class, update this file and **`docs/HOW_IT_WORKS.md`** if behavior changes materially.
