"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";
import { isApprovedSeller } from "@/lib/roles";

export default function MoneyPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const toast = useToast();
  const [summary, setSummary] = useState(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    const data = await apiFetch("/orders/money/summary/");
    setSummary(data);
  }

  useEffect(() => {
    if (loading || !user) return;
    void (async () => {
      try { await load(); }
      catch (e) { if (e instanceof ApiError) toast.error(e.message); }
    })();
  }, [loading, user, toast]);

  useEffect(() => {
    if (!loading && user && !isApprovedSeller(user)) router.replace("/seller/apply");
  }, [loading, user, router]);

  async function saveVerification(partial) {
    setBusy(true);
    try {
      await apiFetch("/orders/seller-verification/", { method: "POST", body: JSON.stringify(partial) });
      await load();
      toast.success("Verification updated.");
    } catch (e) { if (e instanceof ApiError) toast.error(e.message); }
    finally { setBusy(false); }
  }

  async function requestCashout() {
    setBusy(true);
    try {
      await apiFetch("/orders/money/cashout/", { method: "POST", body: "{}" });
      await load();
      toast.success("Cashout request submitted.");
    } catch (e) { if (e instanceof ApiError) toast.error(e.message); }
    finally { setBusy(false); }
  }

  if (loading || !user) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading…</p>
      </div>
    );
  }

  const b = summary?.balance || {};
  const v = summary?.verification || {};

  const checks = [
    ["Connect onboarded", v.connect_onboarded_at],
    ["ID verified",       v.id_verified_at],
    ["SSN verified",      v.ssn_verified_at],
  ];

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
          <h1 className="heading-display text-2xl">Money & Cashout</h1>
        </div>

        {/* Balance cards */}
        <div className="grid gap-3 sm:grid-cols-2 mb-6">
          {[
            ["Escrow total",          b.escrow_total_usd || "0.00", "rgba(255,92,26,0.12)",   "rgba(255,92,26,0.25)",   "var(--primary)"],
            ["Available for payout",  b.net_available_usd || "0.00","rgba(34,197,94,0.12)",  "rgba(34,197,94,0.25)",   "#4ade80"],
          ].map(([label, value, bg, border, color]) => (
            <div key={label} style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "20px" }}>
              <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", fontFamily: "var(--ff-display)", marginBottom: 8 }}>
                {label}
              </p>
              <p className="price-mono" style={{ fontSize: 28, fontWeight: 700, color }}>
                ${Number(value).toFixed(2)}
              </p>
            </div>
          ))}
        </div>

        {Array.isArray(summary?.earnings_lines) && summary.earnings_lines.length > 0 && (
          <div
            className="mb-6 overflow-x-auto"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "20px" }}
          >
            <p style={{ fontSize: 15, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", marginBottom: 12 }}>
              Recent orders (VIN / vehicle)
            </p>
            <table className="w-full text-left text-sm" style={{ borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ color: "var(--text-muted)", fontSize: 11, textTransform: "uppercase", fontFamily: "var(--ff-display)" }}>
                  <th className="py-2 pr-3">#</th>
                  <th className="py-2 pr-3">Part</th>
                  <th className="py-2 pr-3">VIN</th>
                  <th className="py-2 pr-3">Vehicle</th>
                  <th className="py-2 pr-3">$</th>
                  <th className="py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {summary.earnings_lines.map((row) => (
                  <tr key={row.order_id} style={{ borderTop: "1px solid var(--border)" }}>
                    <td className="py-2 pr-3 font-mono">{row.order_id}</td>
                    <td className="py-2 pr-3" style={{ color: "var(--text-secondary)" }}>{row.part_label}</td>
                    <td className="py-2 pr-3 font-mono text-xs">{row.vin || "—"}</td>
                    <td className="py-2 pr-3" style={{ color: "var(--text-secondary)" }}>{row.vehicle_title || "—"}</td>
                    <td className="py-2 pr-3 price-mono">{row.amount_usd}</td>
                    <td className="py-2" style={{ color: "var(--text-muted)" }}>{row.state?.replace(/_/g, " ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Verification */}
        <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "24px" }}>
          <p style={{ fontSize: 15, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", marginBottom: 4 }}>
            Seller verification
          </p>
          <p style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 16 }}>
            Orders can complete before verification. Cashout requires Connect + ID + SSN.
          </p>

          {/* Status dots */}
          <div className="flex flex-wrap gap-3 mb-5">
            {checks.map(([label, verified]) => (
              <div key={label} style={{
                display: "flex", alignItems: "center", gap: 8,
                background: "var(--bg-elevated)", border: "1px solid var(--border)",
                borderRadius: "var(--radius-md)", padding: "6px 14px",
              }}>
                <span style={{
                  width: 8, height: 8, borderRadius: "50%",
                  background: verified ? "#4ade80" : "var(--border-strong)",
                  flexShrink: 0,
                }} />
                <span style={{ fontSize: 12, fontFamily: "var(--ff-display)", color: "var(--text-secondary)", fontWeight: 600 }}>
                  {label}
                </span>
              </div>
            ))}
          </div>

          <div className="flex flex-wrap gap-2 mb-5">
            {[
              ["Mark Connect onboarded", { connect_onboarded: true }],
              ["Mark ID verified",       { id_verified: true }],
              ["Mark SSN verified",      { ssn_verified: true }],
            ].map(([label, payload]) => (
              <button
                key={label}
                type="button"
                disabled={busy}
                onClick={() => void saveVerification(payload)}
                style={{
                  borderRadius: "var(--radius-md)", padding: "8px 16px",
                  fontSize: 12, fontWeight: 600, fontFamily: "var(--ff-display)",
                  background: "var(--bg-elevated)", border: "1px solid var(--border)",
                  color: "var(--text-secondary)", cursor: "pointer", opacity: busy ? 0.5 : 1,
                  transition: "all 0.12s",
                }}
                onMouseEnter={e => { if (!busy) { e.currentTarget.style.borderColor = "rgba(255,92,26,0.4)"; e.currentTarget.style.color = "var(--primary)"; } }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.color = "var(--text-secondary)"; }}
              >
                {label}
              </button>
            ))}
          </div>

          <div style={{ borderTop: "1px solid var(--border)", paddingTop: 16 }}>
            <p style={{ fontSize: 13, color: summary?.payout_ready ? "#4ade80" : "var(--text-muted)", marginBottom: 12, fontWeight: 600 }}>
              Status: {summary?.payout_ready ? "Ready for cashout" : "Verification incomplete"}
            </p>
            <button
              type="button"
              disabled={busy}
              onClick={() => void requestCashout()}
              className="btn-forge"
              style={{ padding: "10px 28px", fontSize: 14, opacity: busy ? 0.6 : 1 }}
            >
              {busy ? "Processing…" : "Request cashout →"}
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
