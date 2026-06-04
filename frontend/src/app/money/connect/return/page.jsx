"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { motion } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { ApiError, apiFetch } from "@/lib/api";

export default function ConnectReturnPage() {
  return (
    <Suspense>
      <ConnectReturnContent />
    </Suspense>
  );
}

function ConnectReturnContent() {
  const router = useRouter();
  const params = useSearchParams();
  const { user, loading } = useAuth();
  const [state, setState] = useState("checking"); // checking | success | incomplete | error
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (loading || !user) return;
    void (async () => {
      try {
        const result = await apiFetch("/orders/connect/refresh/", { method: "POST", body: "{}" });
        if (result.payouts_enabled) {
          setState("success");
          setMessage("Your bank account is connected and payouts are enabled.");
        } else if (result.details_submitted) {
          setState("incomplete");
          setMessage("Details submitted — Stripe is reviewing your account. This usually takes 1–2 business days.");
        } else {
          setState("incomplete");
          setMessage("Onboarding not yet complete. You can finish it from the money page.");
        }
      } catch (e) {
        setState("error");
        if (e instanceof ApiError) setMessage(e.message);
        else setMessage("Could not fetch account status.");
      }

      setTimeout(() => router.replace("/money"), 3500);
    })();
  }, [loading, user, router]);

  const isRefresh = params?.get("refresh") === "1";

  const icon = state === "success" ? "✓" : state === "error" ? "✕" : "…";
  const iconColor = state === "success" ? "#4ade80" : state === "error" ? "#f87171" : "var(--primary)";
  const heading =
    state === "success" ? "Connected!" :
    state === "incomplete" ? "Almost there" :
    state === "error" ? "Something went wrong" :
    isRefresh ? "Refreshing your link…" : "Checking status…";

  return (
    <div className="flex min-h-[calc(100vh-56px)] items-center justify-center px-4">
      <div className="absolute inset-0 mesh-bg pointer-events-none" />
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.35 }}
        className="relative z-10 w-full max-w-sm text-center"
      >
        <div
          className="rounded-[20px] p-8"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
        >
          <div
            style={{
              width: 56, height: 56, borderRadius: "50%",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: state === "checking" ? 20 : 24, fontWeight: 700,
              background: state === "success" ? "rgba(74,222,128,0.12)" : state === "error" ? "rgba(248,113,113,0.12)" : "rgba(255,92,26,0.12)",
              border: `2px solid ${iconColor}`,
              color: iconColor,
              margin: "0 auto 20px",
            }}
          >
            {icon}
          </div>

          <h1 className="heading-display text-xl mb-3">{heading}</h1>

          {message && (
            <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.6, marginBottom: 16 }}>
              {message}
            </p>
          )}

          {state === "checking" && (
            <p style={{ fontSize: 12, color: "var(--text-muted)" }}>Verifying with Stripe…</p>
          )}

          {state !== "checking" && (
            <p style={{ fontSize: 12, color: "var(--text-muted)" }}>
              Redirecting to your money page…
            </p>
          )}
        </div>
      </motion.div>
    </div>
  );
}
