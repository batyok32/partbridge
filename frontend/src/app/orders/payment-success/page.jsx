"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { ApiError, apiFetch } from "@/lib/api";

export default function OrderPaymentSuccessPage() {
  const [phase, setPhase] = useState("loading");
  const [detail, setDetail] = useState("");
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current || typeof window === "undefined") return;
    ran.current = true;
    const params = new URLSearchParams(window.location.search);
    const sessionId = params.get("session_id");
    if (!sessionId) {
      setPhase("error");
      setDetail("Missing session. Return to purchases and try again.");
      return;
    }
    void (async () => {
      try {
        await apiFetch(`/orders/checkout-session/verify/?session_id=${encodeURIComponent(sessionId)}`);
        setPhase("ok");
        window.history.replaceState({}, "", "/orders/payment-success");
      } catch (e) {
        setPhase("error");
        if (e instanceof ApiError) setDetail(e.message);
        else setDetail("Could not confirm payment.");
      }
    })();
  }, []);

  return (
    <div className="mx-auto max-w-lg px-4 sm:px-6 py-16">
      <div
        className="rounded-xl p-8 text-center"
        style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
      >
        {phase === "loading" && (
          <>
            <p className="heading-display text-lg mb-2">Confirming payment…</p>
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>One moment.</p>
          </>
        )}
        {phase === "ok" && (
          <>
            <p className="text-3xl mb-3">✓</p>
            <p className="heading-display text-xl mb-2">Payment successful</p>
            <p className="text-sm mb-6" style={{ color: "var(--text-muted)" }}>
              Your order is paid and moving into escrow. The seller will be notified.
            </p>
            <Link href="/purchases" className="btn-forge inline-flex px-6 py-3 text-sm">
              View purchases
            </Link>
          </>
        )}
        {phase === "error" && (
          <>
            <p className="heading-display text-lg mb-2" style={{ color: "#f87171" }}>Could not confirm</p>
            <p className="text-sm mb-6" style={{ color: "var(--text-muted)" }}>{detail}</p>
            <Link href="/purchases" className="btn-forge inline-flex px-6 py-3 text-sm">
              Back to purchases
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
