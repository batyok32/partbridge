"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";
import { orderStatusLabel } from "@/lib/order-utils";

function formatMoney(v) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(v) || 0);
}

const STATUS_STYLES = {
  pending:   { background: "rgba(251,191,36,0.12)", border: "1px solid rgba(251,191,36,0.3)",  color: "#fbbf24" },
  confirmed: { background: "rgba(255,92,26,0.12)",  border: "1px solid rgba(255,92,26,0.25)",  color: "var(--primary)" },
  shipped:   { background: "rgba(52,211,153,0.1)",  border: "1px solid rgba(52,211,153,0.3)",  color: "#34d399" },
  delivered: { background: "rgba(167,139,250,0.12)", border: "1px solid rgba(167,139,250,0.25)", color: "#a78bfa" },
  cancelled: { background: "rgba(239,68,68,0.12)",  border: "1px solid rgba(239,68,68,0.25)",  color: "#f87171" },
};

function StatusBadge({ status }) {
  const style = STATUS_STYLES[status] || { background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-muted)" };
  return (
    <span style={{ ...style, borderRadius: "999px", padding: "3px 12px", fontSize: 12, fontWeight: 600, fontFamily: "var(--ff-display)" }}>
      {orderStatusLabel(status)}
    </span>
  );
}

const STEPS = ["pending", "confirmed", "shipped", "delivered"];

function OrderStepper({ status }) {
  const current = STEPS.indexOf(status);
  return (
    <div className="flex items-center gap-0">
      {STEPS.map((step, i) => {
        const done = i <= current;
        const active = i === current;
        return (
          <div key={step} className="flex items-center" style={{ flex: i < STEPS.length - 1 ? 1 : "none" }}>
            <div style={{
              width: 28, height: 28, borderRadius: "50%", flexShrink: 0,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 11, fontWeight: 700, fontFamily: "var(--ff-display)",
              background: done ? (active ? "var(--primary)" : "rgba(255,92,26,0.2)") : "var(--bg-elevated)",
              border: done ? `2px solid ${active ? "var(--primary)" : "rgba(255,92,26,0.4)"}` : "2px solid var(--border)",
              color: done ? (active ? "#fff" : "var(--primary)") : "var(--text-muted)",
            }}>
              {done && !active ? "✓" : i + 1}
            </div>
            <div style={{ fontSize: 10, fontWeight: 600, color: done ? "var(--text-secondary)" : "var(--text-muted)", marginLeft: 4, marginRight: 8, whiteSpace: "nowrap", fontFamily: "var(--ff-display)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
              {orderStatusLabel(step)}
            </div>
            {i < STEPS.length - 1 && (
              <div style={{ flex: 1, height: 2, background: i < current ? "rgba(255,92,26,0.35)" : "var(--border)", marginRight: 8 }} />
            )}
          </div>
        );
      })}
    </div>
  );
}

const inputStyle = {
  background: "var(--bg-elevated)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-md)",
  color: "var(--text-primary)",
  padding: "7px 10px",
  fontSize: 13,
  outline: "none",
  fontFamily: "var(--ff-body)",
  width: "100%",
};

const labelStyle = {
  display: "block",
  fontSize: 10,
  fontWeight: 700,
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  color: "var(--text-muted)",
  fontFamily: "var(--ff-display)",
  marginBottom: 4,
};

function SectionHeading({ children }) {
  return (
    <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", fontFamily: "var(--ff-display)", marginBottom: 10 }}>
      {children}
    </p>
  );
}

export default function SellerOrderDetailPage() {
  const { id: rawId } = useParams();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const toast = useToast();
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [trackingForm, setTrackingForm] = useState({ tracking_number: "", carrier: "" });
  const [busySave, setBusySave] = useState(false);

  const id = Number(rawId);

  const load = useCallback(async () => {
    if (!Number.isFinite(id) || id < 1) return;
    const data = await apiFetch(`/orders/sales/${id}/`);
    setOrder(data);
    const firstItem = data.items?.[0];
    setTrackingForm({
      tracking_number: firstItem?.tracking_number || "",
      carrier: firstItem?.carrier || "",
    });
  }, [id]);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login?next=%2Forders");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (authLoading || !user) return;
    void (async () => {
      setLoading(true);
      try {
        await load();
      } catch (e) {
        if (e instanceof ApiError) {
          toast.error(e.message);
          if (e.status === 403 || e.status === 404) router.replace("/orders");
        }
      } finally {
        setLoading(false);
      }
    })();
  }, [authLoading, user, load, router, toast]);

  async function saveTracking(e) {
    e.preventDefault();
    setBusySave(true);
    try {
      await apiFetch(`/orders/${id}/shipping-plan/`, {
        method: "PATCH",
        body: JSON.stringify({
          tracking_number: trackingForm.tracking_number.trim(),
          carrier: trackingForm.carrier.trim(),
        }),
      });
      toast.success("Tracking saved.");
      await load();
    } catch (err) {
      if (err instanceof ApiError) toast.error(err.message);
    } finally {
      setBusySave(false);
    }
  }

  if (authLoading || !user || loading) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading…</p>
      </div>
    );
  }

  if (!order) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Order not found.</p>
        <Link href="/orders" className="btn-forge inline-flex mt-4">← Back to sales</Link>
      </div>
    );
  }

  const needsTracking = order.status === "confirmed" || order.status === "shipped";
  const shipTo = order.ship_to;

  return (
    <div className="mx-auto max-w-2xl px-4 sm:px-6 py-12">
      <Link href="/orders" className="text-sm font-medium" style={{ color: "var(--primary)" }}>
        ← Sales
      </Link>

      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="mt-4 space-y-4"
      >
        {/* Header */}
        <div className="rounded-xl p-5" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
          <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
            <div>
              <p className="section-label mb-1">Sale</p>
              <h1 className="heading-display text-xl">Order #{order.id}</h1>
              <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 3 }}>
                {order.placed_at ? new Date(order.placed_at).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" }) : "—"}
                {order.buyer_name ? ` · Buyer: ${order.buyer_name}` : ""}
              </p>
            </div>
            <StatusBadge status={order.status} />
          </div>
          <OrderStepper status={order.status} />
        </div>

        {/* Items sold */}
        <div className="rounded-xl p-5 space-y-4" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
          <SectionHeading>Items sold</SectionHeading>
          {(order.items || []).map((item) => {
            const v = item.vehicle_info || {};
            const vehicleLine = [v.year, v.make, v.model].filter(Boolean).join(" ");
            return (
              <div key={item.id} className="flex gap-3">
                <div style={{ width: 64, height: 64, borderRadius: 8, overflow: "hidden", flexShrink: 0, background: "var(--bg-elevated)" }}>
                  {item.item_photo_url
                    ? <img src={item.item_photo_url} alt={item.item_title} className="w-full h-full object-cover" />
                    : <div className="w-full h-full flex items-center justify-center" style={{ fontSize: 22 }}>📦</div>
                  }
                </div>
                <div className="flex-1 min-w-0">
                  <p style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", lineHeight: 1.3 }}>
                    {item.item_title || "Part"}
                  </p>
                  {vehicleLine && (
                    <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>{vehicleLine}</p>
                  )}
                  {v.vin && (
                    <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 1 }}>VIN: {v.vin}</p>
                  )}
                  <div className="flex flex-wrap items-center gap-2 mt-2">
                    <span style={{ fontSize: 13, fontWeight: 700, color: "var(--primary-bright)", fontFamily: "var(--ff-display)" }}>
                      {formatMoney(item.price_at_purchase)}
                    </span>
                    {item.condition && (
                      <span style={{ fontSize: 10, fontWeight: 600, background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 4, padding: "1px 6px", color: "var(--text-muted)" }}>
                        {item.condition.replace(/_/g, " ")}
                      </span>
                    )}
                    {item.shipping_size && (
                      <span style={{ fontSize: 10, fontWeight: 600, background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 4, padding: "1px 6px", color: "var(--text-muted)" }}>
                        {item.shipping_size}
                      </span>
                    )}
                    {item.is_delivered && (
                      <span style={{ fontSize: 11, color: "#4ade80", fontWeight: 600 }}>✓ Delivered</span>
                    )}
                    {!item.is_delivered && item.tracking_number && (
                      <span style={{ fontSize: 11, color: "#34d399", fontWeight: 600 }}>✓ {item.carrier} {item.tracking_number}</span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Tracking entry */}
        {needsTracking && (
          <div className="rounded-xl p-5" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
            <SectionHeading>Shipment tracking</SectionHeading>
            {order.items?.[0]?.tracking_number && (
              <p style={{ fontSize: 12, color: "#34d399", marginBottom: 10 }}>
                ✓ Current tracking: {order.items[0].carrier} {order.items[0].tracking_number}
              </p>
            )}
            <form onSubmit={saveTracking} className="space-y-3">
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label style={labelStyle}>Tracking number</label>
                  <input
                    value={trackingForm.tracking_number}
                    onChange={(e) => setTrackingForm((f) => ({ ...f, tracking_number: e.target.value }))}
                    placeholder="1Z999AA10123456784"
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label style={labelStyle}>Carrier</label>
                  <input
                    value={trackingForm.carrier}
                    onChange={(e) => setTrackingForm((f) => ({ ...f, carrier: e.target.value }))}
                    placeholder="UPS / FedEx / USPS"
                    style={inputStyle}
                  />
                </div>
              </div>
              <button
                type="submit"
                disabled={busySave}
                className="btn-forge"
                style={{ padding: "8px 20px", fontSize: 13, opacity: busySave ? 0.5 : 1 }}
              >
                {busySave ? "Saving…" : "Save tracking"}
              </button>
            </form>
          </div>
        )}

        {/* Ship to */}
        {shipTo && (
          <div className="rounded-xl p-5" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
            <SectionHeading>Ship to</SectionHeading>
            <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.7 }}>
              {shipTo.full_name && <p style={{ fontWeight: 600, color: "var(--text-primary)" }}>{shipTo.full_name}</p>}
              {shipTo.line1 && <p>{shipTo.line1}</p>}
              {shipTo.line2 && <p>{shipTo.line2}</p>}
              {(shipTo.city || shipTo.state || shipTo.zip) && (
                <p>{[shipTo.city, shipTo.state, shipTo.zip].filter(Boolean).join(", ")}</p>
              )}
            </div>
          </div>
        )}

        {/* Order financials */}
        <div className="rounded-xl p-5" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
          <SectionHeading>Order financials</SectionHeading>
          <div className="space-y-2">
            {order.subtotal != null && (
              <div className="flex justify-between gap-4">
                <span style={{ fontSize: 13, color: "var(--text-muted)" }}>Parts subtotal</span>
                <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>{formatMoney(order.subtotal)}</span>
              </div>
            )}
            {order.shipping_cost != null && (
              <div className="flex justify-between gap-4">
                <span style={{ fontSize: 13, color: "var(--text-muted)" }}>Shipping collected</span>
                <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>{formatMoney(order.shipping_cost)}</span>
              </div>
            )}
            {order.tax != null && Number(order.tax) > 0 && (
              <div className="flex justify-between gap-4">
                <span style={{ fontSize: 13, color: "var(--text-muted)" }}>Tax</span>
                <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>{formatMoney(order.tax)}</span>
              </div>
            )}
            <div className="flex justify-between gap-4 pt-2" style={{ borderTop: "1px solid var(--border)" }}>
              <span style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>Total charged to buyer</span>
              <span style={{ fontSize: 14, fontWeight: 700, color: "var(--primary-bright)", fontFamily: "var(--ff-display)" }}>{formatMoney(order.total)}</span>
            </div>
          </div>
          {order.payment_status && (
            <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 8 }}>
              Payment: <span style={{ fontWeight: 600, color: order.payment_status === "succeeded" ? "#4ade80" : "var(--text-muted)" }}>{order.payment_status}</span>
            </p>
          )}
          <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 6 }}>
            Payout is held in escrow until the buyer confirms delivery.
          </p>
        </div>

      </motion.div>
    </div>
  );
}
