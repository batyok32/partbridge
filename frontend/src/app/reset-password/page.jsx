"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { motion } from "framer-motion";

import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";

function firstFieldError(val) {
  if (!val) return null;
  return String(Array.isArray(val) ? val[0] : val);
}

function ResetPasswordInner() {
  const router = useRouter();
  const params = useSearchParams();
  const toast = useToast();
  const [uid, setUid] = useState("");
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    const u = params.get("uid");
    const t = params.get("token");
    if (u) setUid(u);
    if (t) setToken(t);
  }, [params]);

  async function onSubmit(e) {
    e.preventDefault();
    setPending(true);
    try {
      await apiFetch("/auth/password-reset/confirm", {
        method: "POST",
        auth: false,
        body: JSON.stringify({ uid, token, new_password: password }),
      });
      toast.success("Password updated. You can sign in.");
      router.push("/login");
    } catch (err) {
      if (err instanceof ApiError) {
        const d = err.body;
        if (typeof d.detail === "string") toast.error(d.detail);
        else if (d.token) toast.error(firstFieldError(d.token) || err.message);
        else if (d.uid) toast.error(firstFieldError(d.uid) || err.message);
        else if (d.new_password) toast.error(firstFieldError(d.new_password) || err.message);
        else toast.error(err.message);
      } else toast.error("Something went wrong.");
    } finally {
      setPending(false);
    }
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

          <h1 className="heading-display text-2xl mb-1">Choose a new password</h1>
          <p className="text-sm mb-8" style={{ color: "var(--text-muted)" }}>
            Use the link from your email — the form is filled from the URL.
          </p>

          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold mb-1.5 uppercase tracking-widest" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }} htmlFor="password">
                New password
              </label>
              <input
                id="password"
                type="password"
                className="input-forge"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
                placeholder="Min. 8 characters"
              />
            </div>

            <button
              type="submit"
              disabled={pending || !uid || !token}
              className="btn-forge w-full mt-2 disabled:opacity-60"
              style={{ padding: "12px 0", fontSize: 14, justifyContent: "center" }}
            >
              {pending ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                  Saving…
                </span>
              ) : "Update password"}
            </button>
          </form>

          <p className="mt-6 text-center text-sm" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-body)" }}>
            <Link href="/login" className="font-semibold transition-colors" style={{ color: "var(--primary)" }}
              onMouseEnter={e => e.currentTarget.style.color = "var(--primary-bright)"}
              onMouseLeave={e => e.currentTarget.style.color = "var(--primary)"}
            >
              Sign in
            </Link>
          </p>
        </div>
      </motion.div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[calc(100vh-56px)] items-center justify-center">
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading…</p>
        </div>
      }
    >
      <ResetPasswordInner />
    </Suspense>
  );
}
