"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getMakesWithCounts } from "@/lib/api";

export default function MakeStrip() {
  const [makes, setMakes] = useState([]);

  useEffect(() => {
    getMakesWithCounts().then(setMakes).catch(() => setMakes([]));
  }, []);

  if (makes.length === 0) return null;

  return (
    <section className="py-16">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-10">
          <span className="section-label justify-center mb-4">Browse by make</span>
          <h2 className="heading-display text-2xl sm:text-3xl mt-2">Popular makes</h2>
        </div>
        <div className="flex flex-wrap justify-center gap-4">
          {makes.slice(0, 12).map((make) => (
            <Link
              key={make.id}
              href={`/search?make=${make.id}`}
              className="flex flex-col items-center gap-2 rounded-[10px] px-5 py-4 min-w-[100px] transition-all"
              style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
            >
              {make.logo_url ? (
                <img src={make.logo_url} alt="" style={{ height: 32, width: "auto", objectFit: "contain" }} />
              ) : (
                <span style={{ fontSize: 22, fontWeight: 800, color: "var(--primary)", fontFamily: "var(--ff-display)" }}>
                  {make.name.charAt(0)}
                </span>
              )}
              <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)" }}>{make.name}</span>
              {make.listing_count != null && (
                <span style={{ fontSize: 10, color: "var(--text-muted)" }}>{make.listing_count} parts</span>
              )}
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
