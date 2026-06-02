import { Suspense } from "react";

export default function PurchaseIssueLayout({ children }) {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-lg px-6 py-16">
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading…</p>
        </div>
      }
    >
      {children}
    </Suspense>
  );
}
