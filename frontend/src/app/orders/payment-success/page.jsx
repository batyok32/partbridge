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
    const piId = params.get("payment_intent");
    const redirectStatus = params.get("redirect_status");

    if (!piId) {
      setPhase("error");
      setDetail("Missing payment reference. Return to purchases and check your order status.");
      return;
    }
    if (redirectStatus === "failed") {
      setPhase("error");
      setDetail("Payment failed. Please try again from your cart.");
      return;
    }

    void (async () => {
      try {
        await apiFetch("/cart/verify-payment/", {
          method: "POST",
          body: JSON.stringify({ payment_intent_id: piId }),
        });
        setPhase("ok");
        window.history.replaceState({}, "", "/orders/payment-success");
      } catch (e) {
        setPhase("error");
        if (e instanceof ApiError) setDetail(e.message);
        else setDetail("Could not confirm payment — check your purchases for order status.");
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
              Your order is confirmed and moving into escrow. The seller will be notified.
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
