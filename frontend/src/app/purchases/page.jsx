"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";

import { OrderPayCard } from "@/components/OrderPayCard";
import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch, apiFetchRaw } from "@/lib/api";
import { isOrderCompleted, isOrderDelivered, orderTabFilter } from "@/lib/order-utils";

const STATE_STYLES = {
  payment_pending: { background: "rgba(251,191,36,0.12)", border: "1px solid rgba(251,191,36,0.3)", color: "#fbbf24" },
  paid_escrow: { background: "rgba(34,197,94,0.12)", border: "1px solid rgba(34,197,94,0.25)", color: "#4ade80" },
  seller_confirmed: { background: "rgba(255,92,26,0.12)", border: "1px solid rgba(255,92,26,0.25)", color: "var(--primary)" },
  label_purchased: { background: "rgba(56,189,248,0.12)", border: "1px solid rgba(56,189,248,0.25)", color: "#38bdf8" },
  shipped: { background: "rgba(52,211,153,0.1)", border: "1px solid rgba(52,211,153,0.3)", color: "#34d399" },
  delivered: { background: "rgba(167,139,250,0.12)", border: "1px solid rgba(167,139,250,0.25)", color: "#a78bfa" },
  refunded: { background: "rgba(239,68,68,0.12)", border: "1px solid rgba(239,68,68,0.25)", color: "#f87171" },
  cancelled: { background: "rgba(239,68,68,0.12)", border: "1px solid rgba(239,68,68,0.25)", color: "#f87171" },
};

function StateBadge({ state }) {
  const style = STATE_STYLES[state] || { background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-muted)" };
  return (
    <span style={{ ...style, borderRadius: "999px", padding: "2px 10px", fontSize: 11, fontWeight: 600, fontFamily: "var(--ff-display)" }}>
      {state?.replace(/_/g, " ")}
    </span>
  );
}

export default function PurchasesPage() {
  const { user, loading: authLoading } = useAuth();
  const toast = useToast();
  const [orders, setOrders] = useState([]);
  const [tab, setTab] = useState("active");

  const load = useCallback(async () => {
    const data = await apiFetch("/orders/purchases/");
    setOrders(Array.isArray(data) ? data : []);
  }, []);

  useEffect(() => {
    if (authLoading || !user) return;
    void (async () => {
      try {
        await load();
      } catch (e) {
        if (e instanceof ApiError) toast.error(e.message);
      }
    })();
  }, [authLoading, user, load, toast]);

  const filtered = useMemo(() => orderTabFilter(orders, tab), [orders, tab]);

  async function downloadReceipt(orderId) {
    try {
      const res = await apiFetchRaw(`/orders/${orderId}/receipt/`);
      if (!res.ok) throw new Error("Could not download receipt.");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `receipt-order-${orderId}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Receipt downloaded.");
    } catch (e) {
      toast.error(e?.message || "Receipt failed.");
    }
  }

  if (authLoading || !user) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading…</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 py-12">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
        <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="section-label mb-1">Buying</p>
            <h1 className="heading-display text-2xl">My purchases</h1>
            <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
              Track orders, message sellers, and download PDF receipts.
            </p>
          </div>
        </div>

        <div className="flex gap-2 mb-5">
          {[
            ["active", "In progress"],
            ["completed", "Completed"],
          ].map(([id, label]) => (
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
            const delivered = isOrderDelivered(o);
            const closed = ["refunded", "cancelled"].includes(o.state);
            const contactHref = `/purchases/${o.id}/issue?type=contact_seller`;
            return (
              <div
                key={o.id}
                style={{
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-lg)",
                  padding: "14px",
                }}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <Link
                        href={`/purchases/${o.id}`}
                        className="text-sm font-semibold hover:underline"
                        style={{ color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}
                      >
                        #{o.id} · {o.vehicle_part_label}
                      </Link>
                      <StateBadge state={o.state} />
                    </div>
                    <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
                      {o.vehicle_year} {o.vehicle_make} {o.vehicle_model}
                      {o.vehicle_vin ? ` · VIN ${o.vehicle_vin}` : ""}
                    </p>
                    <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>
                      ${o.amount_usd}
                      {o.shipping_amount_usd && Number(o.shipping_amount_usd) > 0 ? ` + $${o.shipping_amount_usd} shipping` : ""}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2 justify-end">
                    <Link href={contactHref} className="btn-ghost text-xs py-1.5 px-3" style={{ fontSize: 12 }}>
                      Contact seller
                    </Link>
                    {delivered && (
                      <>
                        <Link href={`/purchases/${o.id}/issue?type=return_item`} className="btn-ghost text-xs py-1.5 px-3" style={{ fontSize: 12 }}>
                          Return
                        </Link>
                        <Link href={`/purchases/${o.id}/issue?type=item_not_received`} className="btn-ghost text-xs py-1.5 px-3" style={{ fontSize: 12 }}>
                          Didn&apos;t receive
                        </Link>
                      </>
                    )}
                    {!delivered && !closed && (
                      <Link href={`/purchases/${o.id}/issue?type=cancel_order`} className="btn-ghost text-xs py-1.5 px-3" style={{ fontSize: 12 }}>
                        Cancel request
                      </Link>
                    )}
                    <Link href={`/purchases/${o.id}`} className="btn-ghost text-xs py-1.5 px-3" style={{ fontSize: 12 }}>
                      Details
                    </Link>
                    <button
                      type="button"
                      className="btn-ghost text-xs py-1.5 px-3"
                      style={{ fontSize: 12 }}
                      onClick={() => void downloadReceipt(o.id)}
                    >
                      Receipt PDF
                    </button>
                  </div>
                </div>
                {o.state === "payment_pending" && (
                  <div className="mt-3 rounded-lg p-3" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}>
                    <p className="text-xs font-bold uppercase tracking-wide mb-2" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
                      Pay with card
                    </p>
                    <OrderPayCard order={o} onSuccess={load} />
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {filtered.length === 0 && (
          <div className="mt-8 text-center py-14 rounded-xl" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
            <p style={{ fontSize: 14, color: "var(--text-muted)" }}>
              {tab === "completed" ? "No completed purchases yet." : "No active purchases."}
            </p>
            <Link href="/browse" className="btn-forge inline-flex mt-4" style={{ padding: "10px 20px", fontSize: 14 }}>
              Browse parts
            </Link>
          </div>
        )}
      </motion.div>
    </div>
  );
}
