"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { motion } from "framer-motion";

import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";

function VerifyEmailInner() {
  const router = useRouter();
  const params = useSearchParams();
  const toast = useToast();
  const qpEmail = params.get("email") ?? "";
  const qpToken = params.get("token");

  const [email, setEmail] = useState(qpEmail);
  const [code, setCode] = useState("");
  const [pending, setPending] = useState(false);
  const [autoTried, setAutoTried] = useState(false);

  useEffect(() => {
    if (qpEmail) setEmail(qpEmail);
  }, [qpEmail]);

  useEffect(() => {
    if (!qpToken || autoTried) return;
    setAutoTried(true);
    setPending(true);
    apiFetch("/auth/verify-email", {
      method: "POST",
      auth: false,
      body: JSON.stringify({ token: qpToken }),
    })
      .then(() => {
        toast.success("Email verified. Please sign in.");
        router.replace("/login");
      })
      .catch((err) => {
        if (err instanceof ApiError) {
          toast.error(typeof err.body.detail === "string" ? err.body.detail : err.message);
        } else toast.error("Verification failed.");
      })
      .finally(() => setPending(false));
  }, [qpToken, autoTried, router, toast]);

  async function onSubmit(e) {
    e.preventDefault();
    setPending(true);
    try {
      await apiFetch("/auth/verify-email", {
        method: "POST",
        auth: false,
        body: JSON.stringify({ email, code }),
      });
      toast.success("Email verified. Please sign in.");
      router.replace("/login");
    } catch (err) {
      if (err instanceof ApiError) {
        toast.error(typeof err.body.detail === "string" ? err.body.detail : err.message);
      } else toast.error("Verification failed.");
    } finally {
      setPending(false);
    }
  }

  async function resend() {
    setPending(true);
    try {
      await apiFetch("/auth/resend-verification", {
        method: "POST",
        auth: false,
        body: JSON.stringify({ email }),
      });
      toast.success("If an account exists for this email, a new code was sent.");
    } catch {
      toast.success("If an account exists for this email, a new code was sent.");
    } finally {
      setPending(false);
    }
  }

  if (qpToken && pending) {
    return (
      <div className="flex min-h-[calc(100vh-56px)] items-center justify-center">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Confirming your email…</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-[calc(100vh-56px)] items-center justify-center px-4 py-16">
      <div className="absolute inset-0 mesh-bg pointer-events-none" />
      <div className="absolute inset-0 grid-pattern opacity-20 pointer-events-none" />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10 w-full max-w-md"
      >
        <div className="rounded-[20px] p-8" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
          <div className="mb-8 flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-[8px]" style={{ background: "var(--primary)" }}>
              <span style={{ fontFamily: "var(--ff-display)", fontWeight: 800, fontSize: 14, color: "#fff" }}>P</span>
            </div>
            <span style={{ fontFamily: "var(--ff-display)", fontWeight: 700, fontSize: 15, color: "var(--text-primary)" }}>Partbridge</span>
          </div>

          <h1 className="heading-display text-2xl mb-1">Verify your email</h1>
          <p className="text-sm mb-8" style={{ color: "var(--text-muted)" }}>
            Enter the six-digit code from your email, or open the link we sent you.
          </p>

          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold mb-1.5 uppercase tracking-widest" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }} htmlFor="email">
                Email
              </label>
              <input
                id="email"
                type="email"
                className="input-forge"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold mb-1.5 uppercase tracking-widest" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }} htmlFor="code">
                Verification code
              </label>
              <input
                id="code"
                inputMode="numeric"
                pattern="[0-9]{6}"
                maxLength={6}
                className="input-forge tracking-widest"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                required
                placeholder="000000"
              />
            </div>

            <button
              type="submit"
              disabled={pending}
              className="btn-forge w-full mt-2 disabled:opacity-60"
              style={{ padding: "12px 0", fontSize: 14, justifyContent: "center" }}
            >
              {pending ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                  Checking…
                </span>
              ) : "Verify"}
            </button>
          </form>

          <button
            type="button"
            onClick={() => void resend()}
            disabled={pending || !email}
            className="mt-3 w-full rounded-[10px] text-sm font-medium transition-colors disabled:opacity-60"
            style={{
              padding: "12px 0",
              fontSize: 14,
              border: "1px solid var(--border)",
              background: "transparent",
              color: "var(--text-primary)",
              fontFamily: "var(--ff-body)",
            }}
            onMouseEnter={e => { e.currentTarget.style.background = "var(--bg-elevated)"; }}
            onMouseLeave={e => { e.currentTarget.style.background = "transparent"; }}
          >
            Resend code
          </button>

          <p className="mt-6 text-center text-sm" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-body)" }}>
            <Link href="/login" className="font-semibold transition-colors" style={{ color: "var(--primary)" }}
              onMouseEnter={e => e.currentTarget.style.color = "var(--primary-bright)"}
              onMouseLeave={e => e.currentTarget.style.color = "var(--primary)"}
            >
              Back to sign in
            </Link>
          </p>
        </div>
      </motion.div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[calc(100vh-56px)] items-center justify-center">
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading…</p>
        </div>
      }
    >
      <VerifyEmailInner />
    </Suspense>
  );
}
