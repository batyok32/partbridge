"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

function BrowseRedirect() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const qs = searchParams.toString();
    router.replace(qs ? `/search?${qs}` : "/search");
  }, [router, searchParams]);

  return <div className="p-10 text-sm" style={{ color: "var(--text-muted)" }}>Redirecting…</div>;
}

export default function BrowsePage() {
  return (
    <Suspense fallback={<div className="p-10 text-sm" style={{ color: "var(--text-muted)" }}>Loading…</div>}>
      <BrowseRedirect />
    </Suspense>
  );
}
