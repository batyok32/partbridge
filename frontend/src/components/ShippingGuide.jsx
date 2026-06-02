"use client";

import { useState } from "react";

const TIERS = [
  {
    id: "small",
    label: "Small",
    weight: "≤ 10 lbs",
    examples: "mirrors, sensors, switches",
    icon: "📦",
    color: "emerald",
    zones: [
      { zone: "Same state · within 40 mi", standard: 12,  nextDay: 24 },
      { zone: "Same state · 40+ mi",        standard: 20,  nextDay: 35 },
      { zone: "National",                    standard: 20,  nextDay: null },
    ],
  },
  {
    id: "medium",
    label: "Medium",
    weight: "10 – 50 lbs",
    examples: "doors, seats, axles",
    icon: "🗃️",
    color: "sky",
    zones: [
      { zone: "Same state · within 40 mi", standard: 25,  nextDay: 50 },
      { zone: "Same state · 40+ mi",        standard: 50,  nextDay: 90 },
      { zone: "National",                    standard: 50,  nextDay: null },
    ],
  },
  {
    id: "large",
    label: "Large",
    weight: "50+ lbs",
    examples: "bumpers, hoods, engines",
    icon: "🚗",
    color: "violet",
    zones: [
      { zone: "Same state · within 40 mi", standard: 100, nextDay: 200 },
      { zone: "Same state · 40+ mi",        standard: 200, nextDay: 350 },
      { zone: "National",                    standard: 220, nextDay: null },
    ],
  },
];

const TIER_COLORS = {
  emerald: { bg: "bg-emerald-50 dark:bg-emerald-950/20", border: "border-emerald-200 dark:border-emerald-800", badge: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-200", icon: "text-emerald-600" },
  sky:     { bg: "bg-sky-50 dark:bg-sky-950/20",         border: "border-sky-200 dark:border-sky-800",         badge: "bg-sky-100 text-sky-800 dark:bg-sky-950/50 dark:text-sky-200",         icon: "text-sky-600"     },
  violet:  { bg: "bg-violet-50 dark:bg-violet-950/20",   border: "border-violet-200 dark:border-violet-800",   badge: "bg-violet-100 text-violet-800 dark:bg-violet-950/50 dark:text-violet-200", icon: "text-violet-600" },
};

function fmt(n) {
  return n == null ? "—" : `$${n}`;
}

/**
 * Renders a "See shipping rates" trigger + modal.
 * Use anywhere you want to show the shipping guide.
 */
export function ShippingGuide({ trigger }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* Trigger */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-emerald-700 hover:underline dark:text-emerald-400"
      >
        {trigger ?? (
          <>
            <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4" aria-hidden>
              <path d="M6.5 3A1.5 1.5 0 0 0 5 4.5v.549l-.838.14a4.5 4.5 0 0 0-3.608 4.906l.09.54a4.5 4.5 0 0 0 4.391 3.732l.031.001A4.5 4.5 0 0 0 9.5 10.5V8h1v2.5a4.5 4.5 0 0 0 4.434 4.369l.031-.001a4.5 4.5 0 0 0 4.391-3.731l.09-.54A4.5 4.5 0 0 0 15.838 5.19L15 5.048V4.5A1.5 1.5 0 0 0 13.5 3h-7ZM9.5 7H7V5h2.5v2Zm1 0V5H13v2h-2.5Z" />
            </svg>
            See shipping rates
          </>
        )}
      </button>

      {/* Modal */}
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal aria-label="Shipping rates">
          {/* Backdrop */}
          <div className="absolute inset-0 bg-black/50" onClick={() => setOpen(false)} />

          <div className="relative z-10 w-full max-w-2xl overflow-y-auto rounded-2xl bg-white shadow-2xl dark:bg-zinc-900 max-h-[90vh]">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-zinc-200 px-6 py-4 dark:border-zinc-800">
              <div>
                <h2 className="text-base font-semibold text-zinc-900 dark:text-white">Shipping rates</h2>
                <p className="mt-0.5 text-xs text-zinc-500">Rates are calculated at checkout based on your ZIP and part size.</p>
              </div>
              <button type="button" onClick={() => setOpen(false)} className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-200">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5"><path d="M18 6 6 18M6 6l12 12" /></svg>
              </button>
            </div>

            {/* Tiers */}
            <div className="grid gap-4 p-6 sm:grid-cols-3">
              {TIERS.map((tier) => {
                const c = TIER_COLORS[tier.color];
                return (
                  <div key={tier.id} className={`rounded-xl border p-4 ${c.bg} ${c.border}`}>
                    {/* Tier header */}
                    <div className="mb-3 flex items-center gap-2">
                      <span className="text-2xl">{tier.icon}</span>
                      <div>
                        <p className={`text-xs font-bold uppercase tracking-wide ${c.icon}`}>{tier.label}</p>
                        <p className="text-xs text-zinc-500 dark:text-zinc-400">{tier.weight}</p>
                      </div>
                    </div>
                    <p className="mb-3 text-[11px] italic text-zinc-500 dark:text-zinc-400">{tier.examples}</p>

                    {/* Zone rows */}
                    <div className="space-y-2">
                      <div className="grid grid-cols-3 gap-1 text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
                        <span>Zone</span><span className="text-center">Standard</span><span className="text-center">Next Day</span>
                      </div>
                      {tier.zones.map((z) => (
                        <div key={z.zone} className="grid grid-cols-3 gap-1 rounded-lg bg-white/70 px-2 py-1.5 dark:bg-zinc-800/50">
                          <span className="text-[11px] leading-tight text-zinc-600 dark:text-zinc-300">{z.zone}</span>
                          <span className="text-center text-sm font-semibold text-zinc-900 dark:text-white">{fmt(z.standard)}</span>
                          <span className={`text-center text-sm font-semibold ${z.nextDay ? "text-zinc-900 dark:text-white" : "text-zinc-400 dark:text-zinc-600"}`}>
                            {z.nextDay ? fmt(z.nextDay) : "N/A"}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Footer note */}
            <div className="border-t border-zinc-200 px-6 py-4 dark:border-zinc-800">
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                <span className="font-semibold text-zinc-700 dark:text-zinc-300">How zones work: </span>
                ZIP-based. Same-state shipping is calculated when buyer and seller share a state.
                Next-day is not available for national (cross-state) shipments.
                Final shipping cost is confirmed at checkout.
              </p>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
