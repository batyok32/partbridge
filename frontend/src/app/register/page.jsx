"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const toast = useToast();
  const [name, setName]       = useState("");
  const [email, setEmail]     = useState("");
  const [phone, setPhone]     = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (!loading && user) router.replace("/dashboard");
  }, [loading, user, router]);

  async function onSubmit(e) {
    e.preventDefault();
    setPending(true);
    try {
      await apiFetch("/auth/register", { method: "POST", auth: false, body: JSON.stringify({ name, email, phone, password }) });
      router.push(`/verify-email?email=${encodeURIComponent(email)}`);
    } catch (err) {
      if (err instanceof ApiError) {
        const d = err.body;
        if (typeof d.detail === "string") toast.error(d.detail);
        else if (d.email && Array.isArray(d.email)) toast.error(String(d.email[0]));
        else if (d.password && Array.isArray(d.password)) toast.error(String(d.password[0]));
        else toast.error(err.message);
      } else toast.error("Something went wrong.");
    } finally {
      setPending(false);
    }
  }

  const labelClass = "block text-xs font-semibold mb-1.5 uppercase tracking-widest";

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

          <h1 className="heading-display text-2xl mb-1">Create your account</h1>
          <p className="text-sm mb-8" style={{ color: "var(--text-muted)" }}>
            We&apos;ll email you a verification code before you can sign in. Everyone starts as a buyer; you can apply to sell after your email is verified.
          </p>

          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <label className={labelClass} style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }} htmlFor="name">Full name</label>
              <input id="name" className="input-forge" value={name} onChange={e => setName(e.target.value)} required autoComplete="name" placeholder="Jane Smith" />
            </div>
            <div>
              <label className={labelClass} style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }} htmlFor="email">Email</label>
              <input id="email" type="email" className="input-forge" value={email} onChange={e => setEmail(e.target.value)} required autoComplete="email" placeholder="you@example.com" />
            </div>
            <div>
              <label className={labelClass} style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }} htmlFor="phone">Phone</label>
              <input id="phone" type="tel" className="input-forge" value={phone} onChange={e => setPhone(e.target.value)} required autoComplete="tel" placeholder="+1 (555) 000-0000" />
            </div>

            <div>
              <label className={labelClass} style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }} htmlFor="password">Password</label>
              <input id="password" type="password" className="input-forge" value={password} onChange={e => setPassword(e.target.value)} required minLength={8} autoComplete="new-password" placeholder="Min. 8 characters" />
            </div>

            <button type="submit" disabled={pending} className="btn-forge w-full mt-2 disabled:opacity-60" style={{ padding: "12px 0", fontSize: 14, justifyContent: "center" }}>
              {pending ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                  Creating account…
                </span>
              ) : "Continue →"}
            </button>
          </form>

          <p className="mt-6 text-center text-sm" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-body)" }}>
            Already have an account?{" "}
            <Link href="/login" className="font-semibold transition-colors" style={{ color: "var(--primary)" }}
              onMouseEnter={e => e.currentTarget.style.color = "var(--primary-bright)"}
              onMouseLeave={e => e.currentTarget.style.color = "var(--primary)"}
            >Sign in</Link>
          </p>
        </div>
      </motion.div>
    </div>
  );
}
