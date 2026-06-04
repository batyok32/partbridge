"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { motion } from "framer-motion";

import CarSelector from "@/components/CarSelector";
import { useBuyerCar } from "@/context/car-context";

export default function HomeCarHero({ stagger }) {
  const router = useRouter();
  const { car, setCar, clearCar, loaded, hasCar } = useBuyerCar();
  const [editing, setEditing] = useState(false);

  async function handleCarSubmit(payload) {
    await setCar(payload);
    const params = new URLSearchParams({
      generation: String(payload.generationId),
      year: String(payload.year),
      compatible_only: "1",
    });
    if (payload.modificationId) params.set("modification", String(payload.modificationId));
    router.push(`/search?${params.toString()}`);
  }

  return (
    <motion.div variants={stagger.item} className="relative z-10 mx-auto mt-10 max-w-4xl">
      <div
        className="rounded-[14px] p-4 sm:p-5"
        style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", boxShadow: "var(--shadow-md)" }}
      >
        {loaded && hasCar && !editing ? (
          <div className="text-center py-2">
            <p style={{ fontSize: 15, color: "var(--text-primary)", fontFamily: "var(--ff-body)" }}>
              Showing parts for your{" "}
              <strong>{car.displayLabel}</strong>
            </p>
            <div className="mt-3 flex flex-wrap items-center justify-center gap-4">
              <Link href="/search" className="btn-forge" style={{ padding: "10px 24px", fontSize: 14, borderRadius: 8 }}>
                Browse parts
              </Link>
              <button
                type="button"
                onClick={() => setEditing(true)}
                style={{ fontSize: 13, color: "var(--primary)", background: "none", border: "none", cursor: "pointer", textDecoration: "underline" }}
              >
                Change car
              </button>
            </div>
          </div>
        ) : (
          <CarSelector
            onSubmit={async (payload) => {
              setEditing(false);
              await handleCarSubmit(payload);
            }}
            submitLabel="Find parts for my car"
          />
        )}
      </div>
      <p className="mt-3 text-xs text-center" style={{ color: "var(--text-disabled)", fontFamily: "var(--ff-body)" }}>
        Fitment-specific marketplace — every listing can show whether it fits your car.
      </p>
    </motion.div>
  );
}
