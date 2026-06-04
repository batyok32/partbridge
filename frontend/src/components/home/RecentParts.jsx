"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import FitmentBadge from "@/components/FitmentBadge";
import { useBuyerCar } from "@/context/car-context";
import { getHomeRecent } from "@/lib/api";

function formatMoney(v) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(v));
}

export default function RecentParts() {
  const { car } = useBuyerCar();
  const [items, setItems] = useState([]);

  useEffect(() => {
    const params = { limit: 12 };
    if (car?.generationId) {
      params.generation = car.generationId;
      if (car.modificationId) params.modification = car.modificationId;
      params.compatible_only = "1";
    }
    getHomeRecent(params).then(setItems).catch(() => setItems([]));
  }, [car?.generationId, car?.modificationId]);

  if (items.length === 0) return null;

  return (
    <section className="py-20" style={{ background: "var(--bg-surface)" }}>
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex items-end justify-between mb-8 gap-4">
          <div>
            <span className="section-label mb-2">Just listed</span>
            <h2 className="heading-display text-3xl sm:text-4xl mt-1">Recently listed parts</h2>
          </div>
          <Link href="/search?sort=newest" style={{ fontSize: 13, color: "var(--primary)", textDecoration: "none", fontWeight: 600 }}>
            View all →
          </Link>
        </div>
        <div className="flex gap-4 overflow-x-auto pb-2 snap-x">
          {items.map((item) => (
            <Link
              key={item.id}
              href={`/browse/parts/${item.id}`}
              className="snap-start shrink-0"
              style={{
                width: 260,
                background: "var(--bg-elevated)",
                border: "1px solid var(--border)",
                borderRadius: 12,
                overflow: "hidden",
                textDecoration: "none",
                color: "inherit",
              }}
            >
              <div style={{ aspectRatio: "16/10", background: "var(--bg-base)", position: "relative" }}>
                {item.primary_photo_url ? (
                  <img src={item.primary_photo_url} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                ) : (
                  <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 28 }}>📦</div>
                )}
                <div style={{ position: "absolute", top: 8, left: 8 }}>
                  <FitmentBadge fitment={item.fitment} generationLabel={car?.generationName} />
                </div>
              </div>
              <div style={{ padding: 12 }}>
                <p style={{ fontSize: 13, fontWeight: 700, lineHeight: 1.3, color: "var(--text-primary)" }}>{item.title}</p>
                <p style={{ fontSize: 15, fontWeight: 700, marginTop: 8, color: "var(--primary)" }}>{formatMoney(item.price)}</p>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
