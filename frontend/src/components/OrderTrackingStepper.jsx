"use client";

/**
 * Visual progress from API `tracking_steps` (see backend orders/tracking_ui.py).
 */
export function OrderTrackingStepper({ steps }) {
  const list = Array.isArray(steps) ? steps : [];
  if (list.length === 0) return null;

  return (
    <div className="mt-4">
      <p
        className="text-xs font-bold uppercase tracking-wide mb-3"
        style={{ color: "var(--text-muted)", fontFamily: "var(--ff-display)" }}
      >
        Order progress
      </p>
      <ol className="relative space-y-0 border-l border-[var(--border)] ml-2 pl-4">
        {list.map((s, i) => (
          <li key={s.key || i} className="pb-4 last:pb-0">
            <span
              className="absolute -left-[5px] mt-1 h-2.5 w-2.5 rounded-full border-2"
              style={{
                borderColor: s.complete || s.current ? "var(--primary)" : "var(--border)",
                background: s.complete ? "var(--primary)" : s.current ? "rgba(255,92,26,0.25)" : "var(--bg-elevated)",
              }}
            />
            <p style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", fontFamily: "var(--ff-display)" }}>
              {s.label}
            </p>
            {s.description ? (
              <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>{s.description}</p>
            ) : null}
            {s.current ? (
              <span
                className="inline-block mt-1 rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide"
                style={{ background: "rgba(255,92,26,0.12)", color: "var(--primary-bright)" }}
              >
                Current step
              </span>
            ) : null}
          </li>
        ))}
      </ol>
    </div>
  );
}
