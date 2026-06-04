"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";
import { isOrderCompleted, isOrderDelivered, orderStatusLabel, orderTabFilter } from "@/lib/order-utils";

function formatMoney(v) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(v));
}

const STATUS_STYLES = {
  pending:   { background: "rgba(251,191,36,0.12)", border: "1px solid rgba(251,191,36,0.3)",   color: "#fbbf24" },
  confirmed: { background: "rgba(255,92,26,0.12)",  border: "1px solid rgba(255,92,26,0.25)",   color: "var(--primary)" },
  shipped:   { background: "rgba(52,211,153,0.10)", border: "1px solid rgba(52,211,153,0.3)",   color: "#34d399" },
  delivered: { background: "rgba(167,139,250,0.12)",border: "1px solid rgba(167,139,250,0.25)", color: "#a78bfa" },
  cancelled: { background: "rgba(239,68,68,0.12)",  border: "1px solid rgba(239,68,68,0.25)",   color: "#f87171" },
};

function StatusBadge({ status }) {
  const style = STATUS_STYLES[status] || { background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-muted)" };
  return (
    <span style={{ ...style, borderRadius: 999, padding: "2px 10px", fontSize: 11, fontWeight: 600, fontFamily: "var(--ff-display)" }}>
      {orderStatusLabel(status)}
    </span>
  );
}

function trackingUrl(carrier, number) {
  if (!number) return null;
  const c = (carrier || "").toLowerCase();
  if (c.includes("ups"))   return `https://www.ups.com/track?tracknum=${number}`;
  if (c.includes("fedex")) return `https://www.fedex.com/fedextrack/?tracknumbers=${number}`;
  if (c.includes("usps"))  return `https://tools.usps.com/go/TrackConfirmAction?tLabels=${number}`;
  if (c.includes("dhl"))   return `https://www.dhl.com/us-en/home/tracking.html?tracking-id=${number}`;
  return null;
}

export default function PurchasesPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const toast = useToast();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("active");

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login?next=/purchases");
  }, [authLoading, user, router]);

  const load = useCallback(async () => {
    const data = await apiFetch("/orders/purchases/");
    setOrders(Array.isArray(data) ? data : []);
  }, []);

  useEffect(() => {
    if (authLoading || !user) return;
    void (async () => {
      setLoading(true);
      try { await load(); } catch (e) { if (e instanceof ApiError) toast.error(e.message); }
      finally { setLoading(false); }
    })();
  }, [authLoading, user, load, toast]);

  const filtered = useMemo(() => orderTabFilter(orders, tab), [orders, tab]);
  const activeCount = useMemo(() => orders.filter(o => !isOrderCompleted(o)).length, [orders]);
  const completedCount = useMemo(() => orders.filter(o => isOrderCompleted(o)).length, [orders]);

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
          {[
            ["active", "In progress", activeCount],
            ["completed", "Completed", completedCount],
          ].map(([id, label, count]) => (
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
                display: "flex", alignItems: "center", gap: 6,
              }}
            >
              {label}
              {!loading && count > 0 && (
                <span style={{
                  fontSize: 10, fontWeight: 700, minWidth: 16, height: 16,
                  borderRadius: 8, background: tab === id ? "var(--primary)" : "var(--border)",
                  color: tab === id ? "#fff" : "var(--text-muted)",
                  display: "inline-flex", alignItems: "center", justifyContent: "center", padding: "0 4px",
                }}>
                  {count}
                </span>
              )}
            </button>
          ))}
        </div>

        {loading ? (
          <div style={{ textAlign: "center", padding: "48px 0" }}>
            <p style={{ color: "var(--text-muted)", fontSize: 13 }}>Loading orders…</p>
          </div>
        ) : filtered.length === 0 ? (
          <div style={{ textAlign: "center", padding: "48px 0", background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)" }}>
            <p style={{ fontSize: 28, marginBottom: 8 }}>📭</p>
            <p style={{ color: "var(--text-muted)", fontSize: 14 }}>
              {tab === "active" ? "No active orders." : "No completed orders."}
            </p>
            <Link href="/search" style={{ color: "var(--primary)", fontSize: 13, marginTop: 8, display: "inline-block" }}>Browse parts →</Link>
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map((o) => {
              const firstItem = o.order_items?.[0];
              const photo = firstItem?.item_photo_url;
              const itemTitle = firstItem?.item_snapshot?.title || `Order #${o.id}`;
              const extraCount = (o.order_items?.length || 1) - 1;

              // Find first tracking number across items
              const shippedItem = o.order_items?.find(oi => oi.tracking_number);
              const hasDispute = o.has_open_dispute;

              return (
                <div
                  key={o.id}
                  style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "14px 16px" }}
                >
                  <div className="flex flex-wrap items-start gap-3">
                    {/* Thumbnail */}
                    <div style={{ width: 52, height: 52, borderRadius: 8, overflow: "hidden", flexShrink: 0, background: "var(--bg-elevated)" }}>
                      {photo ? (
                        <img src={photo} alt={itemTitle} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                      ) : (
                        <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20 }}>📦</div>
                      )}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-3 flex-wrap">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 flex-wrap mb-1">
                            <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>
                              #{o.id} · {itemTitle}{extraCount > 0 ? ` +${extraCount} more` : ""}
                            </span>
                            <StatusBadge status={o.status} />
                            {hasDispute && (
                              <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 4, background: "rgba(251,191,36,0.12)", border: "1px solid rgba(251,191,36,0.3)", color: "#fbbf24" }}>
                                Dispute open
                              </span>
                            )}
                          </div>
                          <p style={{ fontSize: 12, color: "var(--text-muted)" }}>
                            {formatMoney(o.total)} · {new Date(o.placed_at).toLocaleDateString()}
                            {o.order_items?.length > 0 && ` · ${o.order_items.length} item${o.order_items.length !== 1 ? "s" : ""}`}
                          </p>
                          {/* Tracking pill */}
                          {shippedItem && (
                            <p style={{ fontSize: 11, color: "#34d399", marginTop: 3, fontWeight: 600 }}>
                              {shippedItem.carrier && `${shippedItem.carrier} · `}
                              {trackingUrl(shippedItem.carrier, shippedItem.tracking_number) ? (
                                <a href={trackingUrl(shippedItem.carrier, shippedItem.tracking_number)} target="_blank" rel="noopener noreferrer" style={{ color: "#34d399" }}>
                                  {shippedItem.tracking_number}
                                </a>
                              ) : shippedItem.tracking_number}
                            </p>
                          )}
                        </div>
                        <div className="flex flex-wrap gap-2 justify-end shrink-0">
                          <Link
                            href={`/purchases/${o.id}`}
                            style={{ fontSize: 12, fontWeight: 600, padding: "6px 14px", borderRadius: 8, border: "1px solid var(--border)", color: "var(--text-secondary)", textDecoration: "none" }}
                          >
                            View order
                          </Link>
                          {isOrderDelivered(o) && (
                            <Link
                              href={`/purchases/${o.id}/issue`}
                              style={{ fontSize: 12, fontWeight: 600, padding: "6px 14px", borderRadius: 8, border: "1px solid rgba(239,68,68,0.35)", color: "#f87171", textDecoration: "none" }}
                            >
                              Open dispute
                            </Link>
                          )}
                        </div>
                      </div>
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
