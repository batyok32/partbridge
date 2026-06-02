"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { isApprovedSeller } from "@/lib/roles";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";

export default function VehiclesPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const toast = useToast();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!authLoading && user && !isApprovedSeller(user)) router.replace("/seller/apply");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    (async () => {
      try {
        const data = await apiFetch("/vehicles/");
        if (!cancelled) setItems(Array.isArray(data) ? data : data.results || []);
      } catch (e) {
        if (!cancelled && e instanceof ApiError) toast.error(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [user, toast]);

  if (authLoading || !user) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading…</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 sm:px-6 py-12">
      <div className="absolute inset-0 mesh-bg pointer-events-none opacity-30" />

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10"
      >
        <div className="flex flex-wrap items-start justify-between gap-4 mb-8">
          <div>
            <p className="section-label mb-1">Inventory</p>
            <h1 className="heading-display text-2xl">Your Vehicles</h1>
          </div>
          <Link href="/vehicles/new" className="btn-forge" style={{ padding: "9px 20px", fontSize: 13 }}>
            + Add vehicle
          </Link>
        </div>

        {loading ? (
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading vehicles…</p>
        ) : items.length === 0 ? (
          <div className="text-center py-14"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)" }}>
            <p style={{ fontSize: 32, marginBottom: 12 }}>🚗</p>
            <p style={{ color: "var(--text-muted)", fontSize: 14, marginBottom: 16 }}>No vehicles yet.</p>
            <Link href="/vehicles/new" className="btn-forge inline-flex" style={{ padding: "10px 24px", fontSize: 14 }}>
              Add your first vehicle
            </Link>
          </div>
        ) : (
          <ul className="space-y-2">
            {items.map((v, i) => (
              <motion.li
                key={v.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04, duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
              >
                <Link
                  href={`/vehicles/${v.id}`}
                  style={{
                    display: "flex", flexDirection: "column", gap: 8,
                    background: "var(--bg-surface)", border: "1px solid var(--border)",
                    borderRadius: "var(--radius-lg)", padding: "16px 18px",
                    textDecoration: "none", transition: "all 0.12s",
                  }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = "rgba(255,92,26,0.35)"; e.currentTarget.style.background = "var(--bg-elevated)"; }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.background = "var(--bg-surface)"; }}
                >
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <div>
                      <p style={{ fontSize: 15, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>
                        {[v.year, v.make, v.model].filter(Boolean).join(" ") || "Vehicle"}
                      </p>
                      <p style={{ fontFamily: "var(--ff-mono)", fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>{v.vin}</p>
                    </div>
                    <div className="flex flex-wrap gap-3" style={{ fontSize: 12, color: "var(--text-muted)" }}>
                      <span>{v.parts_count ?? 0} parts</span>
                      <span>{v.photos_count ?? 0} photos</span>
                      <span style={{
                        background: "var(--bg-elevated)", border: "1px solid var(--border)",
                        borderRadius: "var(--radius-sm)", padding: "2px 8px",
                        fontSize: 11, fontFamily: "var(--ff-display)", fontWeight: 600,
                        color: "var(--text-secondary)",
                      }}>
                        {v.analytics_status}
                      </span>
                    </div>
                  </div>
                </Link>
              </motion.li>
            ))}
          </ul>
        )}
      </motion.div>
    </div>
  );
}
