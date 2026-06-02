"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";
import { isOrderCompleted, isOrderDelivered, orderStatusLabel, orderTabFilter } from "@/lib/order-utils";

function formatMoney(v) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(v));
}

const STATUS_STYLES = {
  pending:   { background: "rgba(251,191,36,0.12)", border: "1px solid rgba(251,191,36,0.3)", color: "#fbbf24" },
  confirmed: { background: "rgba(56,189,248,0.12)", border: "1px solid rgba(56,189,248,0.3)", color: "#38bdf8" },
  shipped:   { background: "rgba(52,211,153,0.10)", border: "1px solid rgba(52,211,153,0.3)", color: "#34d399" },
  delivered: { background: "rgba(167,139,250,0.12)", border: "1px solid rgba(167,139,250,0.25)", color: "#a78bfa" },
  cancelled: { background: "rgba(239,68,68,0.12)", border: "1px solid rgba(239,68,68,0.25)", color: "#f87171" },
};

function StatusBadge({ status }) {
  const style = STATUS_STYLES[status] || { background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-muted)" };
  return (
    <span style={{ ...style, borderRadius: 999, padding: "2px 10px", fontSize: 11, fontWeight: 600, fontFamily: "var(--ff-display)" }}>
      {orderStatusLabel(status)}
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
      try { await load(); } catch (e) { if (e instanceof ApiError) toast.error(e.message); }
    })();
  }, [authLoading, user, load, toast]);

  const filtered = useMemo(() => orderTabFilter(orders, tab), [orders, tab]);

  if (authLoading || !user) {
    return <div className="mx-auto max-w-4xl px-6 py-16"><p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading…</p></div>;
  }

  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 py-12">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
        <div className="mb-6">
          <p className="section-label mb-1">Buying</p>
          <h1 className="heading-display text-2xl">My purchases</h1>
        </div>

        <div className="flex gap-2 mb-5">
          {[["active", "In progress"], ["completed", "Completed"]].map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              style={{
                fontFamily: "var(--ff-display)", fontSize: 13, fontWeight: 600,
                padding: "7px 16px", borderRadius: 8, cursor: "pointer",
                background: tab === id ? "rgba(255,92,26,0.12)" : "var(--bg-elevated)",
                border: tab === id ? "1px solid rgba(255,92,26,0.35)" : "1px solid var(--border)",
                color: tab === id ? "var(--primary-bright)" : "var(--text-secondary)",
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {filtered.length === 0 ? (
          <div style={{ textAlign: "center", padding: "48px 0", background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)" }}>
            <p style={{ fontSize: 28, marginBottom: 8 }}>📭</p>
            <p style={{ color: "var(--text-muted)", fontSize: 14 }}>
              {tab === "active" ? "No active orders." : "No completed orders."}
            </p>
            <Link href="/browse" style={{ color: "var(--primary)", fontSize: 13, marginTop: 8, display: "inline-block" }}>Browse parts →</Link>
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map((o) => {
              const firstItem = o.order_items?.[0];
              const itemTitle = firstItem?.item_snapshot?.title || `Order #${o.id}`;
              const extraCount = (o.order_items?.length || 1) - 1;
              return (
                <div
                  key={o.id}
                  style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "14px 16px" }}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>
                          #{o.id} · {itemTitle}{extraCount > 0 ? ` +${extraCount} more` : ""}
                        </span>
                        <StatusBadge status={o.status} />
                      </div>
                      <p style={{ fontSize: 12, color: "var(--text-muted)" }}>
                        {formatMoney(o.total)} total · {new Date(o.placed_at).toLocaleDateString()}
                      </p>
                      {o.order_items?.length > 0 && (
                        <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
                          {o.order_items.length} item{o.order_items.length !== 1 ? "s" : ""}
                        </p>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-2 justify-end">
                      <Link
                        href={`/purchases/${o.id}`}
                        style={{
                          fontSize: 12, fontWeight: 600, padding: "6px 14px", borderRadius: 8,
                          border: "1px solid var(--border)", color: "var(--text-secondary)", textDecoration: "none",
                        }}
                      >
                        View order
                      </Link>
                      {isOrderDelivered(o) && (
                        <Link
                          href={`/purchases/${o.id}/issue`}
                          style={{
                            fontSize: 12, fontWeight: 600, padding: "6px 14px", borderRadius: 8,
                            border: "1px solid rgba(239,68,68,0.35)", color: "#f87171", textDecoration: "none",
                          }}
                        >
                          Open dispute
                        </Link>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </motion.div>
    </div>
  );
}
