"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";
import { isApprovedSeller } from "@/lib/roles";
import { orderStatusLabel } from "@/lib/order-utils";

function formatMoney(v) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(v) || 0);
}

const STATUS_STYLES = {
  pending:   { color: "#fbbf24" },
  confirmed: { color: "var(--primary)" },
  shipped:   { color: "#34d399" },
  delivered: { color: "#a78bfa" },
  cancelled: { color: "#f87171" },
};

export default function MoneyPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const toast = useToast();
  const [summary, setSummary] = useState(null);
  const [fetched, setFetched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [connectBusy, setConnectBusy] = useState(false);

  const load = useCallback(async () => {
    const data = await apiFetch("/orders/money/summary/");
    setSummary(data);
    setFetched(true);
  }, []);

  useEffect(() => {
    if (loading || !user) return;
    void (async () => {
      try { await load(); }
      catch (e) { if (e instanceof ApiError) toast.error(e.message); }
    })();
  }, [loading, user, load, toast]);

  useEffect(() => {
    if (!loading && user && !isApprovedSeller(user)) router.replace("/seller/apply");
  }, [loading, user, router]);

  async function startConnectOnboarding() {
    setConnectBusy(true);
    try {
      const { url } = await apiFetch("/orders/connect/onboard/", { method: "POST", body: "{}" });
      window.location.href = url;
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
      else toast.error("Could not start onboarding.");
      setConnectBusy(false);
    }
  }

  async function requestCashout() {
    setBusy(true);
    try {
      const res = await apiFetch("/orders/money/cashout/", { method: "POST", body: "{}" });
      await load();
      toast.success(res.detail || "Cashout initiated.");
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (loading || !user) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading…</p>
      </div>
    );
  }

  const b = summary?.balance || {};
  const connect = summary?.connect || {};
  const payoutReady = summary?.payout_ready === true;
  const feeRate = summary?.platform_fee_rate ? `${(parseFloat(summary.platform_fee_rate) * 100).toFixed(0)}%` : "5%";

  const hasAccount = Boolean(connect.account_id);
  const detailsSubmitted = Boolean(connect.details_submitted);
  const payoutsEnabled = Boolean(connect.payouts_enabled);

  const connectStatus = !hasAccount
    ? { label: "Not connected", color: "var(--text-muted)" }
    : !detailsSubmitted
    ? { label: "Onboarding incomplete", color: "#fbbf24" }
    : !payoutsEnabled
    ? { label: "Verification pending", color: "#fbbf24" }
    : { label: "Active", color: "#4ade80" };

  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 py-12">
      <div className="absolute inset-0 mesh-bg pointer-events-none opacity-30" />

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10"
      >
        <div className="mb-6">
          <p className="section-label mb-1">Earnings</p>
          <h1 className="heading-display text-2xl">Money &amp; Cashout</h1>
        </div>

        {/* Balance cards */}
        <div className="grid gap-3 sm:grid-cols-2 mb-6">
          {[
            { label: "In escrow", value: b.escrow_total_usd, color: "var(--primary)", note: "Confirmed or shipped — awaiting delivery" },
            { label: "Available for payout", value: b.net_available_usd, color: "#4ade80", note: payoutsEnabled ? `From your Stripe Connect balance (after ${feeRate} fee)` : `Delivered orders, after ${feeRate} platform fee` },
          ].map(({ label, value, color, note }) => (
            <div key={label} style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "20px" }}>
              <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", fontFamily: "var(--ff-display)", marginBottom: 8 }}>
                {label}
              </p>
              {fetched ? (
                <p className="price-mono" style={{ fontSize: 28, fontWeight: 700, color }}>
                  {formatMoney(value)}
                </p>
              ) : (
                <div style={{ height: 36, borderRadius: 6, background: "var(--bg-elevated)", width: 120 }} />
              )}
              <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 6 }}>{note}</p>
            </div>
          ))}
        </div>

        {/* Stripe Connect */}
        <div className="mb-6" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "24px" }}>
          <div className="flex flex-wrap items-start justify-between gap-4 mb-4">
            <div>
              <p style={{ fontSize: 15, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", marginBottom: 3 }}>
                Stripe Connect
              </p>
              <p style={{ fontSize: 13, color: "var(--text-muted)" }}>
                Link your bank account to receive payouts. Partbridge collects a {feeRate} platform fee on each sale.
              </p>
            </div>
            <div className="flex items-center gap-2" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)", padding: "5px 12px" }}>
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: connectStatus.color, flexShrink: 0 }} />
              <span style={{ fontSize: 12, fontWeight: 600, color: connectStatus.color, fontFamily: "var(--ff-display)" }}>
                {connectStatus.label}
              </span>
            </div>
          </div>

          {payoutsEnabled ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span style={{ fontSize: 12, color: "#4ade80" }}>✓</span>
                <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>Bank account linked and verified</span>
              </div>
              <div className="flex items-center gap-2">
                <span style={{ fontSize: 12, color: "#4ade80" }}>✓</span>
                <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>Payouts enabled — Stripe pays out automatically on a rolling schedule</span>
              </div>
              <button
                type="button"
                disabled={connectBusy}
                onClick={startConnectOnboarding}
                style={{
                  marginTop: 8, fontSize: 12, color: "var(--text-muted)", background: "none", border: "none",
                  cursor: "pointer", textDecoration: "underline", padding: 0,
                }}
              >
                Update bank account or settings →
              </button>
            </div>
          ) : hasAccount && detailsSubmitted ? (
            <div>
              <p style={{ fontSize: 13, color: "#fbbf24", marginBottom: 12 }}>
                Your details are submitted. Stripe is reviewing your account — this usually takes 1–2 business days.
              </p>
              <button
                type="button"
                disabled={connectBusy}
                onClick={startConnectOnboarding}
                className="btn-forge"
                style={{ padding: "9px 22px", fontSize: 13, opacity: connectBusy ? 0.6 : 1 }}
              >
                {connectBusy ? "Redirecting…" : "Continue onboarding →"}
              </button>
            </div>
          ) : (
            <div>
              <p style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 14 }}>
                Connect your bank account so Partbridge can transfer your earnings after buyers confirm delivery.
              </p>
              <button
                type="button"
                disabled={connectBusy}
                onClick={startConnectOnboarding}
                className="btn-forge"
                style={{ padding: "10px 28px", fontSize: 14, opacity: connectBusy ? 0.6 : 1 }}
              >
                {connectBusy ? "Redirecting to Stripe…" : "Connect bank account →"}
              </button>
            </div>
          )}
        </div>

        {/* Recent sales table */}
        {fetched && Array.isArray(summary?.earnings_lines) && summary.earnings_lines.length > 0 && (
          <div
            className="mb-6 overflow-x-auto"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "20px" }}
          >
            <p style={{ fontSize: 15, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", marginBottom: 12 }}>
              Recent sales
            </p>
            <table className="w-full text-left text-sm" style={{ borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ color: "var(--text-muted)", fontSize: 11, textTransform: "uppercase", fontFamily: "var(--ff-display)" }}>
                  <th className="py-2 pr-4">Order</th>
                  <th className="py-2 pr-4">Part</th>
                  <th className="py-2 pr-4">Vehicle</th>
                  <th className="py-2 pr-4">Amount</th>
                  <th className="py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {summary.earnings_lines.map((row, i) => {
                  const statusStyle = STATUS_STYLES[row.state] || { color: "var(--text-muted)" };
                  return (
                    <tr key={`${row.order_id}-${i}`} style={{ borderTop: "1px solid var(--border)" }}>
                      <td className="py-2 pr-4">
                        <Link
                          href={`/orders/${row.order_id}`}
                          style={{ fontSize: 12, fontFamily: "var(--ff-display)", fontWeight: 700, color: "var(--primary)", textDecoration: "none" }}
                          className="hover:underline"
                        >
                          #{row.order_id}
                        </Link>
                      </td>
                      <td className="py-2 pr-4" style={{ color: "var(--text-secondary)", maxWidth: 200 }}>
                        <p style={{ fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{row.part_label || "—"}</p>
                        {row.vin && <p style={{ fontSize: 10, color: "var(--text-muted)", fontFamily: "var(--ff-display)", marginTop: 1 }}>VIN {row.vin}</p>}
                      </td>
                      <td className="py-2 pr-4" style={{ fontSize: 13, color: "var(--text-secondary)" }}>{row.vehicle_title || "—"}</td>
                      <td className="py-2 pr-4" style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", whiteSpace: "nowrap" }}>
                        {formatMoney(row.amount_usd)}
                      </td>
                      <td className="py-2" style={{ fontSize: 11, fontWeight: 600, fontFamily: "var(--ff-display)", ...statusStyle }}>
                        {orderStatusLabel(row.state)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {fetched && (!summary?.earnings_lines || summary.earnings_lines.length === 0) && (
          <div className="mb-6 rounded-xl py-10 text-center" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
            <p style={{ fontSize: 13, color: "var(--text-muted)" }}>No sales yet.</p>
          </div>
        )}

        {/* On-demand cashout */}
        {payoutsEnabled && (
          <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "24px" }}>
            <p style={{ fontSize: 15, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", marginBottom: 4 }}>
              On-demand cashout
            </p>
            <p style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 16 }}>
              Stripe Express pays out automatically on a rolling schedule. Use this to request an immediate transfer to your bank.
            </p>
            {payoutReady ? (
              <>
                <p style={{ fontSize: 13, color: "#4ade80", marginBottom: 12, fontWeight: 600 }}>
                  {formatMoney(b.net_available_usd)} available
                </p>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void requestCashout()}
                  className="btn-forge"
                  style={{ padding: "10px 28px", fontSize: 14, opacity: busy ? 0.6 : 1 }}
                >
                  {busy ? "Processing…" : "Cash out now →"}
                </button>
              </>
            ) : (
              <p style={{ fontSize: 13, color: "var(--text-muted)" }}>
                No available balance right now.
              </p>
            )}
          </div>
        )}
      </motion.div>
    </div>
  );
}
