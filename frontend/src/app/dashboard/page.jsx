"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { motion } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { isApprovedSeller, isBuyerCapable } from "@/lib/roles";

export default function DashboardPage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <div className="mx-auto max-w-lg px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading…</p>
      </div>
    );
  }

  const isSeller = isApprovedSeller(user);
  const isBuyer  = isBuyerCapable(user);
  const app = user.seller_application;
  const accountTypeLabel = isSeller ? "Buyer & approved seller" : "Buyer";

  const quickLinks = [
    isBuyer  && { href: "/browse",   label: "Browse Parts",   desc: "Search the catalog" },
    isBuyer  && { href: "/cart",     label: "Cart",           desc: "Review your cart" },
    isBuyer  && { href: "/purchases", label: "Purchases",      desc: "Your purchase history" },
    !isSeller && { href: "/seller/apply", label: app?.status === "pending" ? "Seller application (pending)" : "Become a seller", desc: "Apply to list vehicles and parts" },
    isSeller && { href: "/vehicles", label: "My Vehicles",    desc: "Manage donor vehicles" },
    isSeller && { href: "/orders",   label: "Orders",         desc: "Incoming orders" },
    isSeller && { href: "/money",    label: "Money",          desc: "Payouts & earnings" },
    { href: "/inbox", label: "Inbox", desc: "Messages" },
  ].filter(Boolean);

  const labelStyle = {
    fontSize: 10,
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    color: "var(--text-muted)",
    fontFamily: "var(--ff-display)",
    marginBottom: 4,
  };

  return (
    <div className="mx-auto max-w-2xl px-4 sm:px-6 py-12">
      <div className="absolute inset-0 mesh-bg pointer-events-none opacity-40" />

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10"
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-4 mb-8">
          <div>
            <p className="section-label mb-1">Account</p>
            <h1 className="heading-display text-2xl">
              {user.first_name || user.email?.split("@")[0] || "Dashboard"}
            </h1>
            <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
              {user.email}
            </p>
          </div>
          <button
            type="button"
            onClick={() => { logout(); router.push("/"); }}
            style={{
              borderRadius: "var(--radius-md)",
              padding: "8px 16px",
              fontSize: 13,
              fontWeight: 600,
              fontFamily: "var(--ff-display)",
              background: "var(--bg-elevated)",
              border: "1px solid var(--border)",
              color: "var(--text-secondary)",
              cursor: "pointer",
              transition: "all 0.12s",
              marginTop: 4,
              whiteSpace: "nowrap",
            }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = "rgba(239,68,68,0.4)"; e.currentTarget.style.color = "#f87171"; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.color = "var(--text-secondary)"; }}
          >
            Sign out
          </button>
        </div>

        {/* Profile card */}
        <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "24px", marginBottom: 24 }}>
          <p style={{ ...labelStyle, marginBottom: 16 }}>Profile</p>
          <dl className="grid gap-4 sm:grid-cols-2">
            {[
              ["Name",           user.name],
              ["Phone",          user.phone],
              ["Account",        accountTypeLabel],
              ["Seller request", isSeller
                ? "Approved — you can list inventory"
                : app
                  ? ({ pending: "Pending review", approved: "Approved", rejected: "Not approved" }[app.status] || app.status)
                  : "None submitted"],
              ["Email verified", user.email_verified_at
                ? new Date(user.email_verified_at).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" })
                : "Not verified"],
            ].map(([dt, dd]) => (
              <div key={dt}>
                <dt style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", fontFamily: "var(--ff-display)", marginBottom: 3 }}>
                  {dt}
                </dt>
                <dd style={{ fontSize: 14, color: "var(--text-primary)", fontFamily: "var(--ff-body)" }}>
                  {dd || "—"}
                </dd>
              </div>
            ))}
          </dl>
        </div>

        {/* Quick nav */}
        <div>
          <p style={{ ...labelStyle, marginBottom: 12 }}>Quick links</p>
          <div className="grid gap-2 sm:grid-cols-2">
            {quickLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                style={{
                  display: "flex", flexDirection: "column", gap: 2,
                  background: "var(--bg-surface)", border: "1px solid var(--border)",
                  borderRadius: "var(--radius-lg)", padding: "14px 16px",
                  textDecoration: "none", transition: "all 0.12s",
                }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = "rgba(255,92,26,0.35)"; e.currentTarget.style.background = "var(--bg-elevated)"; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.background = "var(--bg-surface)"; }}
              >
                <span style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>
                  {link.label}
                </span>
                <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{link.desc}</span>
              </Link>
            ))}
          </div>
        </div>
      </motion.div>
    </div>
  );
}
