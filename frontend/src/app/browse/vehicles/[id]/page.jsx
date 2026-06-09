"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import SearchItemCard from "@/components/SearchItemCard";
import { useAuth } from "@/context/auth-context";
import { useBuyerCar } from "@/context/car-context";
import { useCart } from "@/context/cart-context";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";

const PAGE_SIZE = 18;

function VehicleGallery({ photoUrls }) {
  const [active, setActive] = useState(0);
  const scrollerRef = useRef(null);
  const n = photoUrls.length;

  useEffect(() => {
    setActive(0);
    if (scrollerRef.current) scrollerRef.current.scrollLeft = 0;
  }, [photoUrls]);

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el || n < 2) return;
    const onScroll = () => {
      const w = el.clientWidth;
      if (w < 1) return;
      setActive(Math.min(Math.max(0, Math.round(el.scrollLeft / w)), n - 1));
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [n]);

  if (n === 0) {
    return (
      <div
        className="aspect-[16/10] w-full overflow-hidden rounded-2xl flex items-center justify-center"
        style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}
      >
        <p style={{ color: "var(--text-muted)", fontSize: 13 }}>No photos</p>
      </div>
    );
  }

  return (
    <div className="relative w-full overflow-hidden rounded-2xl" style={{ border: "1px solid var(--border)" }}>
      <div
        ref={scrollerRef}
        className="flex aspect-[16/10] w-full snap-x snap-mandatory overflow-x-auto overflow-y-hidden [scrollbar-width:none]"
        style={{ touchAction: "pan-x" }}
      >
        {photoUrls.map((url, i) => (
          <div key={i} className="h-full w-full shrink-0 snap-center" style={{ minWidth: "100%" }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={url} alt="" className="h-full w-full object-cover" draggable={false} />
          </div>
        ))}
      </div>
      {n > 1 && (
        <div className="absolute bottom-3 left-0 right-0 flex justify-center gap-1.5 pointer-events-none">
          {photoUrls.map((_, i) => (
            <span
              key={i}
              className="h-1.5 rounded-full transition-all"
              style={{
                width: active === i ? 18 : 6,
                background: active === i ? "#fff" : "rgba(255,255,255,0.4)",
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function normalizePart(p) {
  const photoUrlStrings = (p.photo_urls || [])
    .map((pu) => (typeof pu === "string" ? pu : pu?.url))
    .filter(Boolean);
  return { ...p, photo_urls: photoUrlStrings };
}

export default function BrowseVehiclePage() {
  const { id } = useParams();
  const { user } = useAuth();
  const toast = useToast();
  const cart = useCart();
  const { car } = useBuyerCar();

  const [vehicle, setVehicle] = useState(null);
  const [parts, setParts] = useState([]);
  const [partsCount, setPartsCount] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [partsLoading, setPartsLoading] = useState(false);
  const [error, setError] = useState(null);
  const prevIdRef = useRef(null);

  const [msgText, setMsgText] = useState("");
  const [msgSending, setMsgSending] = useState(false);
  const [msgSent, setMsgSent] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setSearch(searchInput.trim()), 350);
    return () => clearTimeout(t);
  }, [searchInput]);

  useEffect(() => {
    setPage(1);
  }, [search, id]);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    const firstLoad = prevIdRef.current !== String(id);
    if (firstLoad) {
      setLoading(true);
      setError(null);
      prevIdRef.current = String(id);
    } else {
      setPartsLoading(true);
    }

    const qp = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    if (search) qp.set("q", search);

    apiFetch(`/browse/vehicles/${id}/?${qp}`, { auth: false })
      .then((data) => {
        if (cancelled) return;
        setVehicle(data.vehicle || null);
        setParts((Array.isArray(data.parts) ? data.parts : []).map(normalizePart));
        setPartsCount(Number(data.parts_count || 0));
        setTotalPages(Math.max(1, Number(data.parts_total_pages) || 1));
      })
      .catch((e) => {
        if (cancelled) return;
        setError(e instanceof ApiError ? e.message : "Failed to load vehicle.");
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
          setPartsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [id, page, search]);

  async function handleAddToCart(itemId) {
    if (!user) {
      window.location.href = `/login?next=/browse/vehicles/${id}`;
      return;
    }
    try {
      await apiFetch("/cart/", { method: "POST", body: JSON.stringify({ item: itemId }) });
      await cart.refresh();
      toast.success("Added to cart.");
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    }
  }

  async function handleRemoveFromCart(itemId) {
    const cartItemId = cart.getCartItemId(itemId);
    if (!cartItemId) return;
    try {
      await apiFetch(`/cart/${cartItemId}/`, { method: "DELETE" });
      await cart.refresh();
      toast.success("Removed from cart.");
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    }
  }

  async function handleMessage(e) {
    e.preventDefault();
    if (!user) {
      window.location.href = `/login?next=/browse/vehicles/${id}`;
      return;
    }
    if (!msgText.trim() || parts.length === 0) return;
    setMsgSending(true);
    try {
      await apiFetch("/messages/start/", {
        method: "POST",
        body: JSON.stringify({ item_id: parts[0].id, body: msgText.trim() }),
      });
      setMsgSent(true);
      toast.success("Message sent.");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Failed to send message.");
    } finally {
      setMsgSending(false);
    }
  }

  const vehiclePhotoUrls = useMemo(
    () =>
      (vehicle?.photo_urls || [])
        .map((p) => (typeof p === "string" ? p : p?.url))
        .filter(Boolean),
    [vehicle],
  );

  const vehicleName = vehicle
    ? [vehicle.year, vehicle.make, vehicle.model].filter(Boolean).join(" ")
    : "";

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-16">
        <p style={{ color: "var(--text-muted)", fontSize: 13 }}>Loading…</p>
      </div>
    );
  }

  if (error || !vehicle) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 text-center">
        <p style={{ color: "var(--text-muted)", fontSize: 14 }}>{error || "Vehicle not found."}</p>
        <Link
          href="/browse"
          style={{ color: "var(--primary)", fontSize: 13, marginTop: 12, display: "inline-block" }}
        >
          ← Browse
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 sm:px-6 pb-16 pt-6">
      <Link
        href="/browse"
        style={{
          color: "var(--text-muted)",
          fontSize: 12,
          textDecoration: "none",
          display: "inline-flex",
          alignItems: "center",
          gap: 4,
          marginBottom: 20,
        }}
      >
        ← Browse
      </Link>

      {/* Vehicle header */}
      <div className="grid gap-8 lg:grid-cols-2 mb-12">
        <VehicleGallery photoUrls={vehiclePhotoUrls} />

        <div>
          <h1
            style={{
              fontSize: 26,
              fontWeight: 700,
              color: "var(--text-primary)",
              fontFamily: "var(--ff-display)",
              lineHeight: 1.25,
              marginBottom: 4,
            }}
          >
            {vehicleName}
          </h1>

          {vehicle.generation_label && (
            <p style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 12 }}>
              {vehicle.generation_label}
            </p>
          )}

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
            {vehicle.mileage != null && (
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  background: "var(--bg-elevated)",
                  border: "1px solid var(--border)",
                  borderRadius: 6,
                  padding: "3px 9px",
                  color: "var(--text-secondary)",
                }}
              >
                {Number(vehicle.mileage).toLocaleString()} mi
              </span>
            )}
            {vehicle.condition && (
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  background: "var(--bg-elevated)",
                  border: "1px solid var(--border)",
                  borderRadius: 6,
                  padding: "3px 9px",
                  color: "var(--text-secondary)",
                }}
              >
                {vehicle.condition.replace(/_/g, " ")}
              </span>
            )}
            {vehicle.seller_zip && (
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  background: "var(--bg-elevated)",
                  border: "1px solid var(--border)",
                  borderRadius: 6,
                  padding: "3px 9px",
                  color: "var(--text-secondary)",
                }}
              >
                📍 {vehicle.seller_zip}
              </span>
            )}
          </div>

          <p style={{ fontSize: 13, color: "var(--text-secondary)" }}>
            {partsCount} {partsCount === 1 ? "part" : "parts"} available
          </p>
        </div>
      </div>

      {/* Parts section */}
      <section>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-5">
          <h2
            style={{
              fontSize: 18,
              fontWeight: 700,
              color: "var(--text-primary)",
              fontFamily: "var(--ff-display)",
            }}
          >
            Parts for sale
            <span
              style={{ fontSize: 13, fontWeight: 400, color: "var(--text-muted)", marginLeft: 8 }}
            >
              ({partsCount})
            </span>
          </h2>
          <input
            type="search"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search parts…"
            className="input-forge h-9 w-full sm:max-w-xs rounded-lg"
            style={{ fontSize: 13 }}
          />
        </div>

        {partsLoading && (
          <p style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 10 }}>Updating…</p>
        )}

        {parts.length === 0 && !partsLoading ? (
          <p style={{ color: "var(--text-muted)", fontSize: 13 }}>
            {search ? "No parts match your search." : "No parts listed for purchase yet."}
          </p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {parts.map((part) => (
              <SearchItemCard
                key={part.id}
                item={part}
                user={user}
                inCart={cart.itemIds.has(part.id)}
                onAddToCart={handleAddToCart}
                onRemoveFromCart={handleRemoveFromCart}
                carGenerationLabel={car?.displayLabel}
              />
            ))}
          </div>
        )}

        {totalPages > 1 && (
          <div className="mt-8 flex items-center justify-center gap-2">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="rounded-lg border px-3 py-1.5 text-sm font-medium transition-all disabled:opacity-40"
              style={{
                borderColor: "var(--border)",
                background: "var(--bg-elevated)",
                color: "var(--text-primary)",
              }}
            >
              ← Prev
            </button>
            <span style={{ fontSize: 13, color: "var(--text-muted)" }}>
              {page} / {totalPages}
            </span>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="rounded-lg border px-3 py-1.5 text-sm font-medium transition-all disabled:opacity-40"
              style={{
                borderColor: "var(--border)",
                background: "var(--bg-elevated)",
                color: "var(--text-primary)",
              }}
            >
              Next →
            </button>
          </div>
        )}
      </section>

      {/* Message seller */}
      {parts.length > 0 && (
        <section
          className="mt-10 border-t pt-8"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <div
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-xl)",
              padding: 16,
            }}
          >
            <p
              style={{
                fontSize: 14,
                fontWeight: 700,
                fontFamily: "var(--ff-display)",
                color: "var(--text-primary)",
                marginBottom: 8,
              }}
            >
              Message the seller
            </p>

            {msgSent ? (
              <div
                className="flex items-center gap-2 rounded-xl px-4 py-3"
                style={{
                  background: "rgba(34,197,94,0.1)",
                  border: "1px solid rgba(34,197,94,0.3)",
                }}
              >
                <span>✓</span>
                <p style={{ fontSize: 13, color: "#4ade80" }}>
                  Message sent!{" "}
                  <Link
                    href="/inbox"
                    style={{ color: "#4ade80", textDecoration: "underline" }}
                  >
                    View inbox
                  </Link>
                </p>
              </div>
            ) : (
              <form onSubmit={handleMessage}>
                <textarea
                  value={msgText}
                  onChange={(e) => setMsgText(e.target.value)}
                  rows={3}
                  placeholder="Ask about availability, condition, or a specific part…"
                  disabled={msgSending}
                  style={{
                    width: "100%",
                    resize: "vertical",
                    background: "var(--bg-elevated)",
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    padding: "8px 12px",
                    fontSize: 13,
                    color: "var(--text-primary)",
                    fontFamily: "var(--ff-body)",
                    outline: "none",
                  }}
                />
                <button
                  type="submit"
                  disabled={msgSending || !msgText.trim()}
                  style={{
                    marginTop: 8,
                    padding: "8px 20px",
                    fontSize: 13,
                    fontWeight: 600,
                    background: "var(--bg-elevated)",
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    color: "var(--text-secondary)",
                    cursor: "pointer",
                    opacity: msgSending || !msgText.trim() ? 0.5 : 1,
                  }}
                >
                  {msgSending ? "Sending…" : "Send"}
                </button>
              </form>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
