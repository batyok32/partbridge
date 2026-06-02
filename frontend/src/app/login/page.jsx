"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { ApiError } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const { login, user, loading } = useAuth();
  const toast = useToast();
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending]   = useState(false);

  useEffect(() => {
    if (!loading && user) router.replace("/dashboard");
  }, [loading, user, router]);

  async function onSubmit(e) {
    e.preventDefault();
    setPending(true);
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err) {
      if (err instanceof ApiError) {
        const rawCode = err.body.code;
        const code = Array.isArray(rawCode) ? rawCode[0] : rawCode;
        if (code === "email_not_verified") {
          toast.error(
            <span>
              Verify your email first. Check your inbox or request a new code.{" "}
              <Link href={`/verify-email?email=${encodeURIComponent(email)}`} className="font-semibold underline" style={{ color: "var(--primary)" }}>
                Go to verification
              </Link>
            </span>
          );
        } else {
          const d = err.body.detail;
          let detail = null;
          if (typeof d === "string") detail = d;
          else if (Array.isArray(d)) detail = String(d[0]);
          else if (err.body.non_field_errors && Array.isArray(err.body.non_field_errors)) {
            detail = String(err.body.non_field_errors[0]);
          }
          toast.error(detail ?? "Invalid email or password.");
        }
      } else toast.error("Something went wrong.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex min-h-[calc(100vh-56px)] items-center justify-center px-4 py-16">
      {/* Background mesh */}
      <div className="absolute inset-0 mesh-bg pointer-events-none" />
      <div className="absolute inset-0 grid-pattern opacity-20 pointer-events-none" />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10 w-full max-w-md"
      >
        {/* Card */}
        <div className="rounded-[20px] p-8" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
          {/* Logo mark */}
          <div className="mb-8 flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-[8px]" style={{ background: "var(--primary)" }}>
              <span style={{ fontFamily: "var(--ff-display)", fontWeight: 800, fontSize: 14, color: "#fff" }}>P</span>
            </div>
            <span style={{ fontFamily: "var(--ff-display)", fontWeight: 700, fontSize: 15, color: "var(--text-primary)" }}>Partbridge</span>
          </div>

          <h1 className="heading-display text-2xl mb-1">Sign in</h1>
          <p className="text-sm mb-8" style={{ color: "var(--text-muted)" }}>
            Use the email and password you registered with.
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
                onChange={e => setEmail(e.target.value)}
                required
                autoComplete="email"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-semibold uppercase tracking-widest" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }} htmlFor="password">
                  Password
                </label>
                <Link href="/forgot-password" className="text-xs font-medium transition-colors" style={{ color: "var(--primary)", fontFamily: "var(--ff-body)" }}
                  onMouseEnter={e => e.currentTarget.style.color = "var(--primary-bright)"}
                  onMouseLeave={e => e.currentTarget.style.color = "var(--primary)"}
                >
                  Forgot password?
                </Link>
              </div>
              <input
                id="password"
                type="password"
                className="input-forge"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                placeholder="••••••••"
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
                  Signing in…
                </span>
              ) : "Sign in"}
            </button>
          </form>

          <p className="mt-6 text-center text-sm" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-body)" }}>
            New here?{" "}
            <Link href="/register" className="font-semibold transition-colors" style={{ color: "var(--primary)" }}
              onMouseEnter={e => e.currentTarget.style.color = "var(--primary-bright)"}
              onMouseLeave={e => e.currentTarget.style.color = "var(--primary)"}
            >
              Create an account
            </Link>
          </p>
        </div>
      </motion.div>
    </div>
  );
}
