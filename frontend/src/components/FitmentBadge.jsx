"use client";

export default function FitmentBadge({ fitment, generationLabel }) {
  if (!fitment) return null;
  const status = fitment.status || fitment;
  if (status === "fits") {
    return (
      <span
        style={{
          fontSize: 10,
          fontWeight: 700,
          background: "color-mix(in srgb, var(--success) 18%, transparent)",
          color: "var(--success)",
          border: "1px solid color-mix(in srgb, var(--success) 35%, transparent)",
          borderRadius: 4,
          padding: "2px 8px",
        }}
      >
        Fits your {generationLabel || "car"}
      </span>
    );
  }
  if (status === "unknown") {
    return (
      <span
        style={{
          fontSize: 10,
          fontWeight: 600,
          background: "var(--bg-elevated)",
          color: "var(--text-muted)",
          border: "1px solid var(--border)",
          borderRadius: 4,
          padding: "2px 8px",
        }}
      >
        Unknown fitment
      </span>
    );
  }
  return null;
}
