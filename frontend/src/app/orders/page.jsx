"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";
import { isOrderCompleted, orderTabFilter } from "@/lib/order-utils";

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

const STATE_STYLES = {
  payment_pending: { background: "rgba(251,191,36,0.12)", border: "1px solid rgba(251,191,36,0.3)", color: "#fbbf24" },
  paid_escrow: { background: "rgba(34,197,94,0.12)", border: "1px solid rgba(34,197,94,0.25)", color: "#4ade80" },
  seller_confirmed: { background: "rgba(255,92,26,0.12)", border: "1px solid rgba(255,92,26,0.25)", color: "var(--primary)" },
  label_purchased: { background: "rgba(56,189,248,0.12)", border: "1px solid rgba(56,189,248,0.25)", color: "#38bdf8" },
  shipped: { background: "rgba(52,211,153,0.1)", border: "1px solid rgba(52,211,153,0.3)", color: "#34d399" },
  delivered: { background: "rgba(167,139,250,0.12)", border: "1px solid rgba(167,139,250,0.25)", color: "#a78bfa" },
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

/** Min / max pickup calendar date (YYYY-MM-DD) — aligns with backend week window. */
function pickupDateBounds() {
  const now = new Date();
  const tomorrow = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
  const pythonWeekday = (d) => (d.getDay() + 6) % 7;
  const pw = pythonWeekday(now);
  let daysToSun = (6 - pw) % 7;
  const weekEndDay = new Date(now.getFullYear(), now.getMonth(), now.getDate() + daysToSun);
  let weekEnd = weekEndDay;
  const tomorrowTs = new Date(tomorrow.getFullYear(), tomorrow.getMonth(), tomorrow.getDate()).getTime();
  if (weekEnd.getTime() < tomorrowTs) {
    weekEnd = new Date(weekEndDay.getFullYear(), weekEndDay.getMonth(), weekEndDay.getDate() + 7);
  }
  const fmt = (d) => {
    const p = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  };
  return { minDate: fmt(tomorrow), maxDate: fmt(weekEnd) };
}

export default function SellerOrdersPage() {
  const { user, loading: authLoading } = useAuth();
  const toast = useToast();
  const [orders, setOrders] = useState([]);
  const [sellerQueue, setSellerQueue] = useState([]);
  const [busyId, setBusyId] = useState(null);
  const [forms, setForms] = useState({});
  const [tab, setTab] = useState("active");
  const [rescheduleOpen, setRescheduleOpen] = useState({});

  const dateBounds = useMemo(() => pickupDateBounds(), []);

  const loadOrders = useCallback(async () => {
    const data = await apiFetch("/orders/sales/");
    setOrders(Array.isArray(data) ? data : []);
    if (Array.isArray(data)) {
      const next = {};
      for (const o of data) {
        next[o.id] = {
          package_length_in: o.package_length_in || "16",
          package_width_in: o.package_width_in || "12",
          package_height_in: o.package_height_in || "8",
          package_weight_lb: o.package_weight_lb || "11",
          pickup_date: o.pickup_window_start || "",
          pickup_time_start: o.pickup_slot_start ? String(o.pickup_slot_start).slice(0, 5) : "09:00",
          pickup_time_end: o.pickup_slot_end ? String(o.pickup_slot_end).slice(0, 5) : "17:00",
          insurance_opt_in: !!o.insurance_opt_in,
          overage_acknowledged: true,
        };
      }
      setForms(next);
    }
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

  function updateForm(orderId, key, value) {
    setForms((prev) => ({ ...prev, [orderId]: { ...(prev[orderId] || {}), [key]: value } }));
  }

  async function suggestShipping(orderId) {
    setBusyId(orderId);
    try {
      const data = await apiFetch(`/orders/${orderId}/shipping-plan/suggest/`, { method: "POST" });
      setForms((prev) => ({
        ...prev,
        [orderId]: {
          ...(prev[orderId] || {}),
          package_length_in: data.package_length_in,
          package_width_in: data.package_width_in,
          package_height_in: data.package_height_in,
          package_weight_lb: data.package_weight_lb,
          pickup_date: data.pickup_date || prev[orderId]?.pickup_date,
          pickup_time_start: (data.pickup_time_start || "09:00:00").slice(0, 5),
          pickup_time_end: (data.pickup_time_end || "17:00:00").slice(0, 5),
          overage_acknowledged: true,
        },
      }));
      toast.success("Suggested package applied (inches / lb).");
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    } finally {
      setBusyId(null);
    }
  }

  async function saveShipping(orderId) {
    const f = forms[orderId] || {};
    setBusyId(orderId);
    try {
      const toTime = (s, fallback) => {
        const t = (s || "").trim();
        if (t.length === 5 && t.includes(":")) return `${t}:00`;
        if (t.length >= 8) return t;
        return fallback;
      };
      await apiFetch(`/orders/${orderId}/shipping-plan/`, {
        method: "PATCH",
        body: JSON.stringify({
          package_length_in: Number(f.package_length_in),
          package_width_in: Number(f.package_width_in),
          package_height_in: Number(f.package_height_in),
          package_weight_lb: Number(f.package_weight_lb),
          pickup_date: f.pickup_date,
          pickup_time_start: toTime(f.pickup_time_start, "09:00:00"),
          pickup_time_end: toTime(f.pickup_time_end, "17:00:00"),
          insurance_opt_in: !!f.insurance_opt_in,
          overage_acknowledged: !!f.overage_acknowledged,
        }),
      });
      setRescheduleOpen((prev) => ({ ...prev, [orderId]: false }));
      await loadOrders();
      toast.success("Pickup window saved.");
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    } finally {
      setBusyId(null);
    }
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
            Buyer purchases live under <Link href="/purchases" className="underline" style={{ color: "var(--primary)" }}>My purchases</Link>.
            Package size is in inches and pounds; carrier pickup uses a same-day time window.
          </p>
        </div>

        {sellerQueue.length > 0 && (
          <div
            className="mb-5 rounded-[12px] px-4 py-3"
            style={{ background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.25)" }}
          >
            <p style={{ fontSize: 13, fontWeight: 700, color: "#fbbf24", fontFamily: "var(--ff-display)", marginBottom: 6 }}>
              Action required
            </p>
            <div className="space-y-1">
              {sellerQueue.map((q) => (
                <p key={q.id} style={{ fontSize: 12, color: "rgba(251,191,36,0.8)" }}>
                  #{q.id} · {q.part} · {q.needs_pickup_schedule ? "Pickup not scheduled yet" : q.needs_shipment ? "Label / pickup pending" : q.state}
                </p>
              ))}
            </div>
          </div>
        )}

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

        <div className="space-y-2">
          {filtered.map((o) => {
            const hasPickup = Boolean(o.pickup_scheduled_at || o.pickup_scheduled_summary);
            const showForm = !hasPickup || rescheduleOpen[o.id];
            const blocked = o.pickup_reschedule_blocked === true;

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
                        href={`/orders/${o.id}`}
                        className="text-sm font-semibold hover:underline"
                        style={{ color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}
                      >
                        #{o.id} · {o.vehicle_part_label}
                      </Link>
                      <StateBadge state={o.state} />
                    </div>
                    <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>
                      ${o.amount_usd}
                      {o.shipping_amount_usd && Number(o.shipping_amount_usd) > 0 ? ` + $${o.shipping_amount_usd} shipping` : ""}
                    </p>
                    <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
                      {o.vehicle_vin ? `VIN ${o.vehicle_vin}` : ""}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    {user?.id === o.seller && (o.state === "seller_confirmed" || o.state === "label_purchased" || o.state === "paid_escrow") && (
                      <button
                        type="button"
                        disabled={busyId === o.id}
                        onClick={() => void suggestShipping(o.id)}
                        style={{
                          borderRadius: "var(--radius-md)",
                          padding: "6px 14px",
                          fontSize: 12,
                          fontWeight: 600,
                          fontFamily: "var(--ff-display)",
                          background: "var(--bg-elevated)",
                          border: "1px solid var(--border)",
                          color: "var(--text-secondary)",
                          cursor: "pointer",
                          opacity: busyId === o.id ? 0.5 : 1,
                        }}
                      >
                        AI suggest package
                      </button>
                    )}
                  </div>
                </div>

                {user?.id === o.seller && (o.state === "seller_confirmed" || o.state === "label_purchased" || o.state === "paid_escrow") && (
                  <div className="mt-3 rounded-lg p-3" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}>
                    {hasPickup && !showForm && (
                      <div
                        className="mb-3 rounded-md px-3 py-2 flex flex-wrap items-center justify-between gap-2"
                        style={{ background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.25)" }}
                      >
                        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
                          <strong style={{ color: "#4ade80" }}>Pickup scheduled.</strong>{" "}
                          {o.pickup_scheduled_summary || "Window saved."}
                          {blocked ? " Today is pickup day — changes are locked." : " You can reschedule until pickup day."}
                        </p>
                        {!blocked && (
                          <button
                            type="button"
                            className="btn-ghost text-xs py-1.5 px-3"
                            style={{ fontSize: 12 }}
                            onClick={() => setRescheduleOpen((prev) => ({ ...prev, [o.id]: true }))}
                          >
                            Reschedule
                          </button>
                        )}
                      </div>
                    )}

                    {showForm && (
                      <>
                        <p className="text-xs font-bold uppercase tracking-wide mb-2" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}>
                          Package (in / lb) &amp; pickup window
                        </p>
                        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                          {[
                            ["package_length_in", "Length (in)"],
                            ["package_width_in", "Width (in)"],
                            ["package_height_in", "Height (in)"],
                            ["package_weight_lb", "Weight (lb)"],
                          ].map(([key, ph]) => (
                            <div key={key}>
                              <label style={labelStyle}>{ph}</label>
                              <input
                                value={forms[o.id]?.[key] ?? ""}
                                onChange={(e) => updateForm(o.id, key, e.target.value)}
                                inputMode="decimal"
                                style={inputStyle}
                              />
                            </div>
                          ))}
                        </div>
                        <div className="mt-3 grid gap-3 sm:grid-cols-3 max-w-3xl">
                          <div>
                            <label style={labelStyle}>Pickup date</label>
                            <input
                              type="date"
                              min={dateBounds.minDate}
                              max={dateBounds.maxDate}
                              value={forms[o.id]?.pickup_date ?? ""}
                              onChange={(e) => updateForm(o.id, "pickup_date", e.target.value)}
                              style={inputStyle}
                            />
                          </div>
                          <div>
                            <label style={labelStyle}>Window from</label>
                            <input
                              type="time"
                              value={forms[o.id]?.pickup_time_start ?? ""}
                              onChange={(e) => updateForm(o.id, "pickup_time_start", e.target.value)}
                              style={inputStyle}
                            />
                          </div>
                          <div>
                            <label style={labelStyle}>Window to</label>
                            <input
                              type="time"
                              value={forms[o.id]?.pickup_time_end ?? ""}
                              onChange={(e) => updateForm(o.id, "pickup_time_end", e.target.value)}
                              style={inputStyle}
                            />
                          </div>
                        </div>
                        <p className="text-[11px] mt-2" style={{ color: "var(--text-muted)" }}>
                          Date must be tomorrow through Sunday of this week (see min/max). Next-day orders must use the required pickup date from checkout.
                        </p>
                        <button
                          type="button"
                          disabled={busyId === o.id}
                          onClick={() => void saveShipping(o.id)}
                          className="btn-forge mt-3"
                          style={{ padding: "6px 14px", fontSize: 12, opacity: busyId === o.id ? 0.5 : 1 }}
                        >
                          Save shipping plan
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {filtered.length === 0 && (
          <div
            className="mt-8 text-center py-12"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)" }}
          >
            <p style={{ fontSize: 13, color: "var(--text-muted)" }}>
              {tab === "completed" ? "No completed sales yet." : "No active sales."}
            </p>
          </div>
        )}
      </motion.div>
    </div>
  );
}
