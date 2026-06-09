"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useBuyerCar } from "@/context/car-context";
import { getFeaturedCategories } from "@/lib/api";

export default function FeaturedCategories() {
  const { car } = useBuyerCar();
  const [categories, setCategories] = useState([]);

  useEffect(() => {
    const params = {};
    if (car?.generationId) {
      params.generation = car.generationId;
      if (car.modificationId) params.modification = car.modificationId;
      params.compatible_only = "1";
    }
    getFeaturedCategories(params)
      .then((data) => setCategories(data.filter((c) => c.item_count > 0)))
      .catch(() => setCategories([]));
  }, [car?.generationId, car?.modificationId]);

  if (categories.length === 0) return null;

  const suffix = car?.generationName ? ` for your ${car.generationName}` : "";

  return (
    <section className="py-20">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <span className="section-label justify-center mb-4">Shop by category</span>
          <h2 className="heading-display text-3xl sm:text-4xl mt-2">Featured categories</h2>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {categories.map((cat) => (
            <Link
              key={cat.id}
              href={`/search?category=${cat.slug}${car?.generationId ? `&generation=${car.generationId}&compatible_only=1` : ""}`}
              className="rounded-[12px] p-5 transition-all"
              style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
            >
              <p style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>{cat.name}</p>
              <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 6 }}>
                {cat.item_count} listing{cat.item_count !== 1 ? "s" : ""}{suffix}
              </p>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
