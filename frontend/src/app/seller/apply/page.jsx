"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";
import { isApprovedSeller } from "@/lib/roles";

const labelClass = "block text-xs font-semibold mb-1.5 uppercase tracking-widest";

export default function SellerApplyPage() {
  const router = useRouter();
  const { user, loading, refreshUser } = useAuth();
  const toast = useToast();
  const [businessName, setBusinessName] = useState("");
  const [whySell, setWhySell] = useState("");
  const [inventorySummary, setInventorySummary] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  useEffect(() => {
    if (!loading && user && isApprovedSeller(user)) router.replace("/vehicles");
  }, [loading, user, router]);

  const app = user?.seller_application;
  const pendingReview = app?.status === "pending";

  async function onSubmit(e) {
    e.preventDefault();
    setPending(true);
    try {
      await apiFetch("/auth/seller-application", {
        method: "POST",
        body: JSON.stringify({
          business_name: businessName.trim(),
          why_sell: whySell.trim(),
          inventory_summary: inventorySummary.trim(),
        }),
      });
      toast.success("Application submitted.");
      await refreshUser();
      setBusinessName("");
      setWhySell("");
      setInventorySummary("");
    } catch (err) {
      if (err instanceof ApiError) {
        const d = err.body;
        if (typeof d.detail === "string") toast.error(d.detail);
        else toast.error(err.message);
      } else toast.error("Something went wrong.");
    } finally {
      setPending(false);
    }
  }

  if (loading || !user) {
    return (
      <div className="mx-auto max-w-lg px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading…</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-[calc(100vh-56px)] items-start justify-center px-4 py-16">
      <div className="absolute inset-0 mesh-bg pointer-events-none" />
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10 w-full max-w-lg"
      >
        <div className="rounded-[20px] p-8" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
          <p className="section-label mb-2">Selling on Partbridge</p>
          <h1 className="heading-display text-2xl mb-2">Become a seller</h1>
          <p className="text-sm mb-8" style={{ color: "var(--text-muted)" }}>
            New accounts shop as buyers. After we review your application, you can list vehicles and parts.
          </p>

          {!user.email_verified_at && (
            <div
              className="mb-6 rounded-[12px] p-4 text-sm"
              style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}
            >
              Verify your email before applying.{" "}
              <Link href={`/verify-email?email=${encodeURIComponent(user.email)}`} className="font-semibold" style={{ color: "var(--primary)" }}>
                Open verification
              </Link>
            </div>
          )}

          {pendingReview && (
            <div
              className="mb-6 rounded-[12px] p-4 text-sm"
              style={{ background: "rgba(255,92,26,0.08)", border: "1px solid rgba(255,92,26,0.25)", color: "var(--text-secondary)" }}
            >
              Your application is <strong style={{ color: "var(--text-primary)" }}>pending review</strong>. We will follow up by email.
            </div>
          )}

          {app?.status === "rejected" && (
            <div
              className="mb-6 rounded-[12px] p-4 text-sm"
              style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}
            >
              <p className="font-semibold text-red-400 mb-1">Previous application was not approved.</p>
              {app.rejection_reason ? <p>{app.rejection_reason}</p> : <p>You may submit a new application below.</p>}
            </div>
          )}

          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <label className={labelClass} style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }} htmlFor="biz">
                Business or display name <span className="font-normal normal-case">(optional)</span>
              </label>
              <input
                id="biz"
                className="input-forge"
                value={businessName}
                onChange={(e) => setBusinessName(e.target.value)}
                maxLength={200}
                placeholder="e.g. Cascade Auto Recyclers"
              />
            </div>
            <div>
              <label className={labelClass} style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }} htmlFor="why">
                Why do you want to sell here?
              </label>
              <textarea
                id="why"
                className="input-forge min-h-[120px] py-3 resize-y"
                value={whySell}
                onChange={(e) => setWhySell(e.target.value)}
                required
                minLength={20}
                placeholder="A few sentences about your experience and how you will serve buyers."
              />
            </div>
            <div>
              <label className={labelClass} style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }} htmlFor="inv">
                What will you list?
              </label>
              <textarea
                id="inv"
                className="input-forge min-h-[100px] py-3 resize-y"
                value={inventorySummary}
                onChange={(e) => setInventorySummary(e.target.value)}
                required
                minLength={10}
                placeholder="Vehicle types, parts sources (yard, fleet, etc.), and roughly how often you add inventory."
              />
            </div>

            <button
              type="submit"
              disabled={pending || pendingReview || !user.email_verified_at}
              className="btn-forge w-full mt-2 disabled:opacity-60"
              style={{ padding: "12px 0", fontSize: 14, justifyContent: "center" }}
            >
              {pending ? "Submitting…" : pendingReview ? "Application pending" : "Submit application"}
            </button>
          </form>

          <p className="mt-6 text-center text-sm" style={{ color: "var(--text-muted)" }}>
            <Link href="/dashboard" className="font-semibold" style={{ color: "var(--primary)" }}>Back to dashboard</Link>
          </p>
        </div>
      </motion.div>
    </div>
  );
}
