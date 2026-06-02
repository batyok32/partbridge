"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiError, apiFetch } from "@/lib/api";

export default function SellerPublicProfilePage() {
  const params = useParams();
  const id = params?.id;
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const raw = (id ?? "").toString().trim();
    const n = Number(raw);
    if (!Number.isFinite(n) || n <= 0) {
      setLoading(false);
      setErr("Invalid seller.");
      return;
    }
    let cancelled = false;
    setLoading(true);
    setErr(null);
    void (async () => {
      try {
        const j = await apiFetch(`/sellers/${n}/public/`, { auth: false });
        if (!cancelled) setData(j);
      } catch (e) {
        if (!cancelled) {
          if (e instanceof ApiError && e.status === 404) setErr("Seller not found.");
          else if (e instanceof ApiError) setErr(e.message);
          else setErr("Could not load seller.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (loading) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading seller…</p>
      </div>
    );
  }

  if (err || !data) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>{err || "Not found."}</p>
        <Link href="/browse" className="mt-4 inline-block text-sm font-medium hover:underline" style={{ color: "var(--primary)" }}>
          ← Browse parts
        </Link>
      </div>
    );
  }

  const ratingLine =
    data.rating_count > 0 && data.rating_avg != null
      ? `${data.rating_avg.toFixed(2)} ★ (${data.rating_count} reviews)`
      : "No reviews yet";

  return (
    <div className="mx-auto max-w-2xl px-6 py-12">
      <p className="section-label mb-1">Seller</p>
      <h1 className="heading-display text-2xl mb-2">{data.display_name}</h1>
      <p className="text-sm" style={{ color: "var(--text-muted)" }}>
        Member since {data.member_since || "—"}
      </p>

      <dl className="mt-8 space-y-3 rounded-xl border p-5" style={{ borderColor: "var(--border)", background: "var(--bg-surface)" }}>
        <div className="flex justify-between gap-4">
          <dt style={{ fontSize: 13, color: "var(--text-muted)" }}>Rating</dt>
          <dd style={{ fontSize: 14, color: "var(--text-primary)" }}>{ratingLine}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt style={{ fontSize: 13, color: "var(--text-muted)" }}>Completed part sales</dt>
          <dd className="price-mono" style={{ fontSize: 14 }}>{data.completed_sales ?? 0}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt style={{ fontSize: 13, color: "var(--text-muted)" }}>Active Buy Now listings</dt>
          <dd className="price-mono" style={{ fontSize: 14 }}>{data.active_buy_now_listings ?? 0}</dd>
        </div>
      </dl>

      <p className="mt-6 text-sm" style={{ color: "var(--text-secondary)" }}>
        Contact sellers through message threads on part listings. Checkout always happens on the listing page.
      </p>

      <Link href="/browse" className="mt-8 inline-block text-sm font-medium hover:underline" style={{ color: "var(--primary)" }}>
        ← Browse parts
      </Link>
    </div>
  );
}
