"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";

import { ApiError, apiFetch } from "@/lib/api";

function formatMoney(v) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(v));
}

function Stars({ value, size = 14 }) {
  const filled = Math.round(Number(value) || 0);
  return (
    <span style={{ fontSize: size, letterSpacing: 1 }}>
      {Array.from({ length: 5 }, (_, i) => (
        <span key={i} style={{ color: i < filled ? "#fbbf24" : "var(--border)" }}>★</span>
      ))}
    </span>
  );
}

function RatingBar({ star, count, total }) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0;
  return (
    <div className="flex items-center gap-2" style={{ fontSize: 12 }}>
      <span style={{ color: "var(--text-muted)", width: 16, textAlign: "right" }}>{star}★</span>
      <div className="flex-1 rounded-full overflow-hidden" style={{ height: 6, background: "var(--bg-elevated)" }}>
        <div
          className="h-full rounded-full"
          style={{ width: `${pct}%`, background: "var(--primary)", transition: "width 0.4s" }}
        />
      </div>
      <span style={{ color: "var(--text-muted)", width: 24, textAlign: "right" }}>{count}</span>
    </div>
  );
}

function ListingCard({ item }) {
  const vehicleLine = [item.vehicle_year, item.vehicle_make, item.vehicle_model].filter(Boolean).join(" ");
  return (
    <Link
      href={`/browse/parts/${item.id}`}
      style={{ textDecoration: "none", display: "block", background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", overflow: "hidden" }}
    >
      <div style={{ aspectRatio: "4/3", background: "var(--bg-elevated)", overflow: "hidden" }}>
        {item.primary_photo_url ? (
          <img src={item.primary_photo_url} alt={item.title} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center" style={{ fontSize: 28 }}>📦</div>
        )}
      </div>
      <div style={{ padding: "10px 12px" }}>
        <p style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)", lineHeight: 1.3, marginBottom: 2 }}>
          {item.title}
        </p>
        {vehicleLine && <p style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 4 }}>{vehicleLine}</p>}
        <div className="flex items-center justify-between">
          <span style={{ fontSize: 14, fontWeight: 700, color: "var(--primary-bright)", fontFamily: "var(--ff-display)" }}>
            {formatMoney(item.price)}
          </span>
          {item.condition && (
            <span style={{ fontSize: 10, fontWeight: 600, background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 4, padding: "1px 6px", color: "var(--text-muted)" }}>
              {item.condition.replace(/_/g, " ")}
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}

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
    return () => { cancelled = true; };
  }, [id]);

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading seller…</p>
      </div>
    );
  }

  if (err || !data) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-16">
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>{err || "Not found."}</p>
        <Link href="/browse" className="mt-4 inline-block text-sm font-medium hover:underline" style={{ color: "var(--primary)" }}>
          ← Browse parts
        </Link>
      </div>
    );
  }

  const ratingTotal = data.rating_count || 0;
  const breakdown = data.rating_breakdown || {};
  const listings = data.active_listings || [];
  const reviews = data.recent_reviews || [];
  const vehicles = data.vehicles || [];

  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 py-12">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }} className="space-y-8">

        {/* Header */}
        <div className="rounded-xl p-6 space-y-4" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
          <div>
            <p className="section-label mb-1">Seller profile</p>
            <h1 className="heading-display text-2xl mb-1">{data.display_name}</h1>
            <p style={{ fontSize: 13, color: "var(--text-muted)" }}>Member since {data.member_since || "—"}</p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {/* Rating summary */}
            <div>
              <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", marginBottom: 8 }}>
                Rating
              </p>
              {ratingTotal > 0 ? (
                <div className="flex items-center gap-3 mb-3">
                  <span style={{ fontSize: 28, fontWeight: 700, fontFamily: "var(--ff-display)", color: "var(--text-primary)" }}>
                    {(data.rating_avg || 0).toFixed(1)}
                  </span>
                  <div>
                    <Stars value={data.rating_avg || 0} size={16} />
                    <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>{ratingTotal} reviews</p>
                  </div>
                </div>
              ) : (
                <p style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 8 }}>No reviews yet</p>
              )}
              {ratingTotal > 0 && (
                <div className="space-y-1.5">
                  {[5, 4, 3, 2, 1].map((r) => (
                    <RatingBar key={r} star={r} count={breakdown[r] ?? 0} total={ratingTotal} />
                  ))}
                </div>
              )}
            </div>

            {/* Stats */}
            <dl className="space-y-2">
              <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", marginBottom: 8 }}>
                Stats
              </p>
              <div className="flex justify-between gap-4">
                <dt style={{ fontSize: 13, color: "var(--text-muted)" }}>Completed sales</dt>
                <dd style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>{data.completed_sales ?? 0}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt style={{ fontSize: 13, color: "var(--text-muted)" }}>Active listings</dt>
                <dd style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>{listings.length}</dd>
              </div>
            </dl>
          </div>
        </div>

        {/* Vehicles being broken */}
        {vehicles.length > 0 && (
          <div>
            <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", marginBottom: 10 }}>
              Currently breaking
            </p>
            <div className="flex flex-wrap gap-2">
              {vehicles.map((v) => (
                <Link
                  key={v.id}
                  href={`/search?vehicle=${v.id}`}
                  style={{
                    fontSize: 12, fontWeight: 600, padding: "5px 12px", borderRadius: 8,
                    background: "var(--bg-elevated)", border: "1px solid var(--border)",
                    color: "var(--text-secondary)", textDecoration: "none",
                  }}
                >
                  {v.year} {v.make_name} {v.model_name}
                  {v.generation_name ? ` ${v.generation_name}` : ""}
                  <span style={{ color: "var(--text-muted)", fontWeight: 400 }}> · {v.active_items_count} parts</span>
                </Link>
              ))}
            </div>
          </div>
        )}

        {/* Active listings grid */}
        {listings.length > 0 && (
          <div>
            <div className="flex items-center justify-between gap-4 mb-4">
              <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)" }}>
                Active listings
              </p>
              <Link
                href={`/search?seller=${id}`}
                style={{ fontSize: 12, color: "var(--primary)", textDecoration: "none", fontWeight: 600 }}
              >
                View all →
              </Link>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {listings.slice(0, 12).map((item) => (
                <ListingCard key={item.id} item={item} />
              ))}
            </div>
          </div>
        )}

        {listings.length === 0 && (
          <div className="rounded-xl py-10 text-center" style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
            <p style={{ fontSize: 13, color: "var(--text-muted)" }}>No active listings right now.</p>
          </div>
        )}

        {/* Recent reviews */}
        {reviews.length > 0 && (
          <div>
            <p style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", marginBottom: 10 }}>
              Recent reviews
            </p>
            <div className="space-y-3">
              {reviews.map((rev, i) => (
                <div key={i} style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-xl)", padding: "12px 14px" }}>
                  <div className="flex items-center justify-between gap-3 mb-2">
                    <div className="flex items-center gap-2">
                      <Stars value={rev.rating} size={12} />
                      <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-primary)" }}>
                        {rev.buyer_name}
                      </span>
                    </div>
                    <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{rev.created_at}</span>
                  </div>
                  {rev.body && (
                    <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.55, marginBottom: rev.item_title ? 6 : 0 }}>
                      {rev.body}
                    </p>
                  )}
                  {rev.item_title && (
                    <p style={{ fontSize: 11, color: "var(--text-muted)" }}>For: {rev.item_title}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

      </motion.div>
    </div>
  );
}
