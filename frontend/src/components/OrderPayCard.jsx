"use client";

import { useState } from "react";

import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";

function StubPayButton({ onConfirm, busy }) {
  return (
    <div className="space-y-2">
      <p className="text-xs" style={{ color: "var(--text-muted)" }}>
        Stripe is not configured on the server (dev stub). Use the button below to simulate payment.
      </p>
      <button
        type="button"
        onClick={() => void onConfirm()}
        disabled={busy}
        className="w-full rounded-lg py-2 text-xs font-semibold"
        style={{ border: "1px solid var(--border)", background: "var(--bg-elevated)", color: "var(--text-secondary)" }}
      >
        Simulate payment (dev)
      </button>
    </div>
  );
}

/**
 * Pay for a payment_pending order: hosted Stripe Checkout redirect, or dev stub.
 */
export function OrderPayCard({ order, onSuccess }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  const stripeCheckout = Boolean(order.stripe_checkout_available);
  const isCash = (order.payment_method || "").toLowerCase() === "cash";

  async function confirmCashTest() {
    setBusy(true);
    try {
      await apiFetch(`/orders/${order.id}/confirm-cash-payment/`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      toast.success(`Marked paid (cash test) · order #${order.id}`);
      await onSuccess();
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function confirmStub() {
    setBusy(true);
    try {
      await apiFetch(`/orders/${order.id}/confirm-payment/`, {
        method: "POST",
        body: JSON.stringify({
          payment_intent_id: (order.stripe_payment_intent_id || "").trim() || "",
          status: "succeeded",
        }),
      });
      toast.success(`Paid · order #${order.id}`);
      await onSuccess();
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function startStripeCheckout() {
    setBusy(true);
    try {
      const r = await apiFetch(`/orders/${order.id}/stripe-checkout/`, { method: "POST" });
      const url = r?.url;
      if (typeof url === "string" && url.startsWith("http")) {
        window.location.href = url;
        return;
      }
      toast.error("Checkout did not return a valid URL.");
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (isCash) {
    return (
      <div className="space-y-2">
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          Cash (test mode): confirm when you complete the handoff — no card charge.
        </p>
        <button
          type="button"
          disabled={busy}
          onClick={() => void confirmCashTest()}
          className="btn-forge w-full"
          style={{ padding: "10px 0", fontSize: 13, justifyContent: "center", opacity: busy ? 0.7 : 1 }}
        >
          {busy ? "Saving…" : "Confirm cash payment"}
        </button>
      </div>
    );
  }

  if (!stripeCheckout) {
    return <StubPayButton onConfirm={() => void confirmStub()} busy={busy} />;
  }

  return (
    <div className="space-y-2">
      <p className="text-xs" style={{ color: "var(--text-muted)" }}>
        You will be redirected to Stripe to enter your card securely.
      </p>
      <button
        type="button"
        disabled={busy}
        onClick={() => void startStripeCheckout()}
        className="btn-forge w-full"
        style={{ padding: "10px 0", fontSize: 13, justifyContent: "center", opacity: busy ? 0.7 : 1 }}
      >
        {busy ? "Opening…" : "Pay with Stripe"}
      </button>
    </div>
  );
}
