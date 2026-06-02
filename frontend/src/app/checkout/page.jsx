"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";

import { OrderPayCard } from "@/components/OrderPayCard";
import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";

const inputStyle = {
  background: "var(--bg-elevated)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-md)",
  color: "var(--text-primary)",
  padding: "8px 12px",
  fontSize: 14,
  outline: "none",
  fontFamily: "var(--ff-body)",
  width: "100%",
};

const labelStyle = {
  display: "block",
  fontSize: 10,
  fontWeight: 700,
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  color: "var(--text-muted)",
  fontFamily: "var(--ff-display)",
  marginBottom: 4,
};

function CheckoutContent() {
  const search = useSearchParams();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const toast = useToast();

  const partId = useMemo(() => {
    const raw = (search.get("part") || "").trim();
    const n = Number(raw);
    return Number.isFinite(n) && n > 0 ? n : null;
  }, [search]);

  const [fitmentVerified, setFitmentVerified] = useState(false);
  const [returnPolicyRead, setReturnPolicyRead] = useState(false);
  const [shippingMode, setShippingMode] = useState("standard");
  const [buyerState, setBuyerState] = useState("WA");
  const [buyerZip, setBuyerZip] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("cash");
  const [order, setOrder] = useState(null);
  const [busy, setBusy] = useState(false);
  const [partCheck, setPartCheck] = useState({ status: "idle" });

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login?next=%2Fcheckout");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!partId || !user) {
      setPartCheck({ status: "idle" });
      return;
    }
    let cancelled = false;
    setPartCheck({ status: "loading" });
    void (async () => {
      try {
        const p = await apiFetch(`/browse/parts/${partId}/`, { auth: false });
        if (cancelled) return;
        const eff = p.listing_state_effective || p.listing_state;
        if (eff === "buy_now")
          setPartCheck({
            status: "ok",
            label: p.label,
            pickupAllowed: !!p.vehicle_public?.pickup_allowed,
          });
        else setPartCheck({ status: "blocked", reason: eff === "sold" ? "sold" : "not_for_sale", label: p.label });
      } catch (e2) {
        if (cancelled) return;
        if (e2 instanceof ApiError && e2.status === 404) setPartCheck({ status: "blocked", reason: "gone" });
        else if (e2 instanceof ApiError) setPartCheck({ status: "blocked", reason: "error", detail: e2.message });
        else setPartCheck({ status: "blocked", reason: "gone" });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [partId, user]);

  useEffect(() => {
    const raw = (search.get("shipping") || "").trim().toLowerCase();
    if (raw === "standard" || raw === "next_day" || raw === "pickup") setShippingMode(raw);
  }, [search]);

  useEffect(() => {
    if (partCheck.status !== "ok") return;
    if (shippingMode === "pickup" && partCheck.pickupAllowed === false) setShippingMode("standard");
  }, [partCheck, shippingMode]);

  async function createIntent(e) {
    e.preventDefault();
    if (!partId || partCheck.status === "blocked" || partCheck.status === "loading") return;
    setBusy(true);
    try {
      const data = await apiFetch("/orders/checkout-intent/", {
        method: "POST",
        body: JSON.stringify({
          vehicle_part_id: partId,
          fitment_verified: fitmentVerified,
          return_policy_read: returnPolicyRead,
          shipping_mode: shippingMode,
          buyer_state: buyerState,
          buyer_zip: buyerZip,
          payment_method: paymentMethod,
        }),
      });
      setOrder(data);
    } catch (e2) {
      if (e2 instanceof ApiError) toast.error(e2.message);
    } finally {
      setBusy(false);
    }
  }

  if (authLoading || !user) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading checkout…</p>
      </div>
    );
  }

  const checkoutBlocked =
    !partId ||
    partCheck.status === "blocked" ||
    partCheck.status === "loading" ||
    (partId && partCheck.status === "idle");

  return (
    <div className="mx-auto max-w-xl px-4 sm:px-6 py-12">
      <div className="absolute inset-0 mesh-bg pointer-events-none opacity-30" />

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10"
      >
        <div className="mb-6">
          <p className="section-label mb-1">Purchase</p>
          <h1 className="heading-display text-2xl">Checkout</h1>
          <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
            Part ID: {partId || "—"}
            {partCheck.label ? ` · ${partCheck.label}` : ""}
          </p>
        </div>

        {partId && (partCheck.status === "loading" || partCheck.status === "idle") && (
          <p className="mb-3 text-xs" style={{ color: "var(--text-muted)" }}>Checking listing…</p>
        )}
        {partId && partCheck.status === "blocked" && (
          <div
            className="mb-4 rounded-xl px-3 py-2.5 text-sm"
            style={{
              background: "rgba(245,158,11,0.1)",
              border: "1px solid rgba(245,158,11,0.25)",
              color: "#fbbf24",
            }}
          >
            {partCheck.reason === "sold" && "This part has been sold and is no longer available for purchase."}
            {partCheck.reason === "not_for_sale" && "This listing is not available for Buy Now."}
            {partCheck.reason === "gone" && "This listing is no longer available (sold or removed)."}
            {partCheck.reason === "error" && (partCheck.detail || "Could not load listing.")}
            <Link href="/browse" className="ml-2 font-semibold underline" style={{ color: "var(--primary)" }}>Browse parts</Link>
          </div>
        )}

        <form onSubmit={createIntent} className="space-y-4"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "24px", opacity: checkoutBlocked ? 0.55 : 1, pointerEvents: checkoutBlocked ? "none" : "auto" }}>

          {/* Checkboxes */}
          {[
            [fitmentVerified, setFitmentVerified, "I verified fitment for my vehicle and understand compatibility risk."],
            [returnPolicyRead, setReturnPolicyRead, "I read and accept the seller return policy shown on the listing."],
          ].map(([checked, setter, label]) => (
            <label key={label} style={{ display: "flex", alignItems: "flex-start", gap: 12, cursor: "pointer" }}>
              <div
                style={{
                  marginTop: 1,
                  width: 18,
                  height: 18,
                  borderRadius: 4,
                  border: checked ? "none" : "1.5px solid var(--border-strong)",
                  background: checked ? "var(--primary)" : "var(--bg-elevated)",
                  flexShrink: 0,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  transition: "all 0.12s",
                }}
              >
                {checked && <svg width="10" height="8" viewBox="0 0 10 8" fill="none"><path d="M1 4l3 3 5-6" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>}
              </div>
              <input type="checkbox" checked={checked} onChange={(e) => setter(e.target.checked)} className="sr-only" />
              <span style={{ fontSize: 14, color: "var(--text-secondary)", fontFamily: "var(--ff-body)" }}>{label}</span>
            </label>
          ))}

          {/* Shipping mode */}
          <div>
            <label style={labelStyle}>Shipping</label>
            <select value={shippingMode} onChange={(e) => setShippingMode(e.target.value)} style={inputStyle}>
              <option value="standard">Standard delivery</option>
              <option value="next_day">Next-day delivery (where available)</option>
              {(partCheck.status !== "ok" || partCheck.pickupAllowed) && (
                <option value="pickup">Local pickup (when seller offers it)</option>
              )}
            </select>
            <p style={{ marginTop: 4, fontSize: 12, color: "var(--text-muted)" }}>
              ZIP is required for delivery. Local pickup appears only when the seller enabled it for this vehicle.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label style={labelStyle}>Buyer state</label>
              <input value={buyerState} onChange={(e) => setBuyerState(e.target.value.toUpperCase())} maxLength={2} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>Buyer ZIP</label>
              <input value={buyerZip} onChange={(e) => setBuyerZip(e.target.value)} placeholder="98101" style={inputStyle} />
            </div>
          </div>

          <div>
            <label style={labelStyle}>Payment</label>
            <select
              value={paymentMethod}
              onChange={(e) => setPaymentMethod(e.target.value)}
              style={inputStyle}
            >
              <option value="cash">Cash (test — no card charge)</option>
              <option value="stripe">Card (Stripe)</option>
            </select>
            <p style={{ marginTop: 4, fontSize: 12, color: "var(--text-muted)" }}>
              Cash mode completes the order flow for testing; confirm payment after handoff.
            </p>
          </div>

          <button
            type="submit"
            disabled={busy || checkoutBlocked}
            className="btn-forge w-full"
            style={{ padding: "12px 0", fontSize: 14, justifyContent: "center", opacity: (busy || checkoutBlocked) ? 0.6 : 1 }}
          >
            {busy ? (
              <span className="flex items-center justify-center gap-2">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                Creating…
              </span>
            ) : "Create order →"}
          </button>
        </form>

        {order && (
          <div className="mt-4 space-y-3" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "20px" }}>
            <p className="section-label mb-3">Pay</p>
            <dl className="space-y-2">
              {[
                ["Order", `#${order.id}`],
                ["Payment", (order.payment_method || "").toLowerCase() === "cash" ? "Cash (test)" : "Card (Stripe)"],
                ["Total", `$${order.amount_usd}${order.shipping_amount_usd != null && Number(order.shipping_amount_usd) > 0 ? ` (incl. shipping $${order.shipping_amount_usd})` : ""}`],
                ["State", order.state],
              ].map(([dt, dd]) => (
                <div key={dt} className="flex gap-2">
                  <dt style={{ fontSize: 12, color: "var(--text-muted)", minWidth: 60 }}>{dt}:</dt>
                  <dd className="price-mono" style={{ fontSize: 13, color: "var(--text-primary)" }}>{dd}</dd>
                </div>
              ))}
            </dl>
            {order.payout_blocked && (
              <p className="mt-2 text-sm" style={{ color: "#fbbf24" }}>
                Payout blocked: {order.payout_block_reason}
              </p>
            )}

            <OrderPayCard
              order={order}
              onSuccess={async () => {
                setOrder(null);
                router.push("/orders");
              }}
            />
          </div>
        )}

        <div className="mt-5 flex gap-4 text-sm" style={{ color: "var(--text-muted)" }}>
          <Link href="/browse" style={{ color: "var(--primary)", textDecoration: "none" }}
            onMouseEnter={e => e.currentTarget.style.color = "var(--primary-bright)"}
            onMouseLeave={e => e.currentTarget.style.color = "var(--primary)"}>
            ← Browse parts
          </Link>
          <span>·</span>
          <Link href="/orders" style={{ color: "var(--primary)", textDecoration: "none" }}
            onMouseEnter={e => e.currentTarget.style.color = "var(--primary-bright)"}
            onMouseLeave={e => e.currentTarget.style.color = "var(--primary)"}
          >
            View orders
          </Link>
        </div>
      </motion.div>
    </div>
  );
}

export default function CheckoutPage() {
  return (
    <Suspense fallback={
      <div className="mx-auto max-w-2xl px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading checkout…</p>
      </div>
    }>
      <CheckoutContent />
    </Suspense>
  );
}
