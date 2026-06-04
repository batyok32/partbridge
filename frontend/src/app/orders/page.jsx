"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";
import { orderTabFilter, orderStatusLabel } from "@/lib/order-utils";

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
  const style = STATUS_STYLES[status] || {
    background: "var(--bg-elevated)",
    border: "1px solid var(--border)",
    color: "var(--text-muted)",
  };
  return (
    <span style={{ ...style, borderRadius: "999px", padding: "2px 10px", fontSize: 11, fontWeight: 600, fontFamily: "var(--ff-display)" }}>
      {orderStatusLabel(status)}
    </span>
  );
}

const inputStyle = {
  background: "var(--bg-elevated)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-md)",
  color: "var(--text-primary)",
  padding: "6px 10px",
  fontSize: 12,
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

export default function SellerOrdersPage() {
  const { user, loading: authLoading } = useAuth();
  const toast = useToast();
  const [orders, setOrders] = useState([]);
  const [sellerQueue, setSellerQueue] = useState([]);
  const [busyId, setBusyId] = useState(null);
  const [trackingForms, setTrackingForms] = useState({});
  const [tab, setTab] = useState("active");

  const loadOrders = useCallback(async () => {
    const data = await apiFetch("/orders/sales/");
    const list = Array.isArray(data) ? data : [];
    setOrders(list);
    const next = {};
    for (const o of list) {
      next[o.id] = {
        tracking_number: (o.items?.[0]?.tracking_number) || "",
        carrier: (o.items?.[0]?.carrier) || "",
      };
    }
    setTrackingForms(next);

    const queue = await apiFetch("/orders/seller/action-queue/");
    setSellerQueue(Array.isArray(queue) ? queue : []);
  }, []);

  useEffect(() => {
    if (authLoading || !user) return;
    void (async () => {
      try {
        await loadOrders();
      } catch (e) {
        if (e instanceof ApiError) toast.error(e.message);
      }
    })();
  }, [authLoading, user, loadOrders, toast]);

  async function saveTracking(orderId) {
    setBusyId(orderId);
    try {
      const f = trackingForms[orderId] || {};
      await apiFetch(`/orders/${orderId}/shipping-plan/`, {
        method: "PATCH",
        body: JSON.stringify({
          tracking_number: f.tracking_number || "",
          carrier: f.carrier || "",
        }),
      });
      await loadOrders();
      toast.success("Tracking saved.");
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    } finally {
      setBusyId(null);
    }
  }

  function updateForm(orderId, key, value) {
    setTrackingForms((prev) => ({ ...prev, [orderId]: { ...(prev[orderId] || {}), [key]: value } }));
  }

  const filtered = useMemo(() => orderTabFilter(orders, tab), [orders, tab]);

  if (authLoading || !user) {
    return (
      <div className="mx-auto max-w-6xl px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading…</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-12">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      >
        <div className="mb-6">
          <p className="section-label mb-1">Selling</p>
          <h1 className="heading-display text-2xl">Sales &amp; fulfillment</h1>
          <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
            Buyer purchases live under{" "}
            <Link href="/purchases" className="underline" style={{ color: "var(--primary)" }}>My purchases</Link>.
          </p>
        </div>

        {sellerQueue.length > 0 && (
          <div className="mb-5 rounded-[12px] px-4 py-3" style={{ background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.25)" }}>
            <p style={{ fontSize: 13, fontWeight: 700, color: "#fbbf24", fontFamily: "var(--ff-display)", marginBottom: 6 }}>
              Action required — {sellerQueue.length} item{sellerQueue.length !== 1 ? "s" : ""} need shipment info
            </p>
            <div className="space-y-1">
              {sellerQueue.map((q) => (
                <p key={`${q.id}-${q.part}`} style={{ fontSize: 12, color: "rgba(251,191,36,0.8)" }}>
                  <Link href={`/orders/${q.id}`} style={{ color: "rgba(251,191,36,0.9)", textDecoration: "underline" }}>
                    #{q.id}
                  </Link>{" "}
                  · {q.part} · Tracking not entered yet
                </p>
              ))}
            </div>
          </div>
        )}

        <div className="flex gap-2 mb-5">
          {[["active", "In progress"], ["completed", "Completed"]].map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className="rounded-lg px-4 py-2 text-sm font-semibold transition-colors"
              style={{
                fontFamily: "var(--ff-display)",
                background: tab === id ? "rgba(255,92,26,0.12)" : "var(--bg-elevated)",
                border: tab === id ? "1px solid rgba(255,92,26,0.35)" : "1px solid var(--border)",
                color: tab === id ? "var(--primary-bright)" : "var(--text-secondary)",
              }}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="space-y-3">
          {filtered.map((o) => {
            const needsAction = o.status === "confirmed" || o.status === "shipped";
            const isDelivered = o.status === "delivered";
            const f = trackingForms[o.id] || {};
            const firstItem = o.items?.[0];
            const hasTracking = Boolean(firstItem?.tracking_number);

            return (
              <div
                key={o.id}
                style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", padding: "16px" }}
              >
                {/* Order header */}
                <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <Link
                        href={`/orders/${o.id}`}
                        style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", textDecoration: "none" }}
                        className="hover:underline"
                      >
                        Order #{o.id}
                      </Link>
                      <StatusBadge status={o.status} />
                    </div>
                    <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 3 }}>
                      {o.placed_at ? new Date(o.placed_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : ""}
                      {o.buyer_name ? ` · ${o.buyer_name}` : ""}
                      {o.shipping_address_text ? ` · ${o.shipping_address_text}` : ""}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>
                      {formatMoney(o.total)}
                    </span>
                    <Link
                      href={`/orders/${o.id}`}
                      style={{ fontSize: 12, color: "var(--primary)", textDecoration: "none", fontWeight: 600 }}
                    >
                      Details →
                    </Link>
                  </div>
                </div>

                {/* Line items summary */}
                <div className="space-y-2 mb-3">
                  {(o.items || []).map((item) => (
                    <div key={item.id} className="flex items-center justify-between gap-2">
                      <p style={{ fontSize: 13, color: "var(--text-secondary)", fontWeight: 600 }}>{item.item_title || "Part"}</p>
                      <div className="flex items-center gap-2">
                        {item.shipping_size && (
                          <span style={{ fontSize: 10, fontWeight: 600, background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 4, padding: "1px 6px", color: "var(--text-muted)" }}>
                            {item.shipping_size}
                          </span>
                        )}
                        {item.is_delivered && (
                          <span style={{ fontSize: 11, color: "#4ade80" }}>✓ Delivered</span>
                        )}
                        {!item.is_delivered && item.tracking_number && (
                          <span style={{ fontSize: 11, color: "#34d399" }}>✓ Tracking added</span>
                        )}
                        <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{formatMoney(item.price_at_purchase)}</span>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Tracking entry */}
                {needsAction && (
                  <div
                    className="rounded-lg p-3"
                    style={{
                      background: !hasTracking ? "rgba(245,158,11,0.05)" : "var(--bg-elevated)",
                      border: !hasTracking ? "1px solid rgba(245,158,11,0.25)" : "1px solid var(--border)",
                    }}
                  >
                    {hasTracking ? (
                      <p style={{ fontSize: 12, color: "#34d399", marginBottom: 8 }}>
                        ✓ Tracking on file: {firstItem.carrier} {firstItem.tracking_number}
                      </p>
                    ) : (
                      <p style={{ fontSize: 11, fontWeight: 600, color: "#fbbf24", marginBottom: 8, fontFamily: "var(--ff-display)" }}>
                        Tracking required
                      </p>
                    )}
                    <div className="grid gap-2 sm:grid-cols-2 max-w-md mb-3">
                      <div>
                        <label style={labelStyle}>Tracking number</label>
                        <input
                          value={f.tracking_number ?? ""}
                          onChange={(e) => updateForm(o.id, "tracking_number", e.target.value)}
                          placeholder="1Z999AA10123456784"
                          style={inputStyle}
                        />
                      </div>
                      <div>
                        <label style={labelStyle}>Carrier</label>
                        <input
                          value={f.carrier ?? ""}
                          onChange={(e) => updateForm(o.id, "carrier", e.target.value)}
                          placeholder="UPS / FedEx / USPS"
                          style={inputStyle}
                        />
                      </div>
                    </div>
                    <button
                      type="button"
                      disabled={busyId === o.id}
                      onClick={() => void saveTracking(o.id)}
                      className="btn-forge"
                      style={{ padding: "6px 16px", fontSize: 12, opacity: busyId === o.id ? 0.5 : 1 }}
                    >
                      {busyId === o.id ? "Saving…" : "Save tracking"}
                    </button>
                  </div>
                )}

                {isDelivered && firstItem?.tracking_number && (
                  <p style={{ fontSize: 12, color: "#4ade80", marginTop: 4 }}>
                    ✓ Delivered · {firstItem.carrier} {firstItem.tracking_number}
                  </p>
                )}
              </div>
            );
          })}
        </div>

        {filtered.length === 0 && (
          <div className="mt-8 text-center py-12" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)" }}>
            <p style={{ fontSize: 13, color: "var(--text-muted)" }}>
              {tab === "completed" ? "No completed sales yet." : "No active sales."}
            </p>
          </div>
        )}
      </motion.div>
    </div>
  );
}
