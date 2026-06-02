"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

import { BrowsePartCard } from "@/components/BrowsePartCard";
import { PartsPickerMulti } from "@/components/PartsPickerMulti";
import { ShippingGuide } from "@/components/ShippingGuide";
import { useAuth } from "@/context/auth-context";
import { useToast } from "@/context/toast-context";
import { ApiError, apiFetch } from "@/lib/api";
import { effectivePartBuyPrice } from "@/lib/part-pricing";

const BROWSE_PREFS_KEY = "partbridge_browse_prefs_v2";
const PARTS_PAGE_SIZE = 12;

/** Compact page indices + ellipsis (0-based current page). */
function browseVehiclePartsPaginationEntries(totalPages, currentPage0) {
  if (totalPages <= 1) return [];
  if (totalPages <= 9) {
    return Array.from({ length: totalPages }, (_, i) => i);
  }
  const pages = new Set([0, totalPages - 1]);
  for (let i = currentPage0 - 1; i <= currentPage0 + 1; i++) {
    if (i >= 0 && i < totalPages) pages.add(i);
  }
  for (let i = 0; i < 2; i++) pages.add(i);
  for (let i = totalPages - 2; i < totalPages; i++) pages.add(i);
  const sorted = [...pages].sort((a, b) => a - b);
  const out = [];
  let prev = -2;
  for (const p of sorted) {
    if (prev >= 0 && p - prev > 1) out.push("ellipsis");
    out.push(p);
    prev = p;
  }
  return out;
}

function readSavedZip() {
  if (typeof window === "undefined") return "";
  try {
    const raw = localStorage.getItem(BROWSE_PREFS_KEY);
    if (!raw) return "";
    const j = JSON.parse(raw);
    return typeof j.buyerZip === "string" ? j.buyerZip : "";
  } catch {
    return "";
  }
}

// ─── Inline state badge labels (design tokens — readable on light & dark) ────
const STATE_LABELS = {
  sold: {
    label: "Sold",
    chip: {
      background: "var(--bg-hover)",
      color: "var(--text-secondary)",
      border: "1px solid var(--border)",
      textDecoration: "line-through",
    },
  },
  unavailable: {
    label: "Unavailable",
    chip: {
      background: "var(--danger-muted)",
      color: "var(--danger)",
      border: "1px solid color-mix(in srgb, var(--danger) 28%, transparent)",
    },
  },
  sold_elsewhere: {
    label: "Sold elsewhere",
    chip: {
      background: "var(--warning-muted)",
      color: "var(--warning)",
      border: "1px solid color-mix(in srgb, var(--warning) 35%, transparent)",
    },
  },
};

export default function PublicDonorVehiclePage() {
  const { id } = useParams();
  const router = useRouter();
  const { user } = useAuth();
  const toast = useToast();

  const [vehicle, setVehicle] = useState(null);
  const [parts, setParts] = useState([]);
  const [otherListableParts, setOtherListableParts] = useState([]);
  const [partsCount, setPartsCount] = useState(0);
  const [partsPage, setPartsPage] = useState(1);
  const [partsTotalPages, setPartsTotalPages] = useState(1);
  const [partsSearchInput, setPartsSearchInput] = useState("");
  const [partsSearch, setPartsSearch] = useState("");
  const [inactiveParts, setInactiveParts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [partsRefreshing, setPartsRefreshing] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const lastLoadedVehicleIdRef = useRef(null);
  const [activePhoto, setActivePhoto] = useState(0);
  const [buyerZip, setBuyerZip] = useState("");
  const [shippingByPart, setShippingByPart] = useState({});

  // Gallery touch swipe
  const touchStartX = useRef(null);

  // Buy-now part detail modal
  const [partModal, setPartModal] = useState(null); // part object
  const [modalShipMode, setModalShipMode] = useState("standard");
  const modalListingEff = partModal
    ? partModal.listing_state_effective || partModal.listing_state
    : null;
  const modalBuyPrice = partModal ? effectivePartBuyPrice(partModal) : null;
  const modalListNum =
    partModal && partModal.price != null && partModal.price !== ""
      ? Number(partModal.price)
      : null;
  const modalShowOffer =
    modalBuyPrice != null &&
    modalListNum != null &&
    Number.isFinite(modalListNum) &&
    Math.abs(modalBuyPrice - modalListNum) > 0.005;
  const modalCanBuyNow = Boolean(
    partModal && modalListingEff === "buy_now" && modalBuyPrice != null,
  );

  // Similar cars
  const [similarCars, setSimilarCars] = useState([]);

  // Inactive parts search
  const [inactiveQ, setInactiveQ] = useState("");

  // Message form
  const [msgText, setMsgText] = useState("");
  const [msgSending, setMsgSending] = useState(false);
  const [msgSent, setMsgSent] = useState(false);
  const [selectedMsgParts, setSelectedMsgParts] = useState([]);
  const msgManuallyEdited = useRef(false);

  const messageBaseHref = user ? "/inbox" : "/login?next=%2Fbrowse";

  useEffect(() => {
    setBuyerZip(readSavedZip());
  }, []);

  useLayoutEffect(() => {
    lastLoadedVehicleIdRef.current = null;
    setPartsPage(1);
    setPartsSearchInput("");
    setPartsSearch("");
  }, [id]);

  useEffect(() => {
    const t = setTimeout(() => setPartsSearch(partsSearchInput.trim()), 400);
    return () => clearTimeout(t);
  }, [partsSearchInput]);

  useEffect(() => {
    setPartsPage(1);
  }, [partsSearch]);

  // Load vehicle + parts (Buy now list only; server search + pagination)
  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    const idStr = String(id);
    const isPartsOnlyRefetch =
      lastLoadedVehicleIdRef.current != null &&
      lastLoadedVehicleIdRef.current === idStr;

    (async () => {
      if (isPartsOnlyRefetch) {
        setPartsRefreshing(true);
      } else {
        setLoading(true);
      }
      setLoadError(null);
      try {
        const z = readSavedZip();
        const qp = new URLSearchParams();
        if (z.trim()) qp.set("buyer_zip", z.trim());
        qp.set("buy_now_only", "1");
        qp.set("page", String(partsPage));
        qp.set("page_size", String(PARTS_PAGE_SIZE));
        if (partsSearch) qp.set("q", partsSearch);
        const qs = qp.toString();
        const data = await apiFetch(`/browse/vehicles/${id}/?${qs}`, {
          auth: false,
        });
        if (cancelled) return;
        setVehicle(data.vehicle || null);
        setParts(Array.isArray(data.parts) ? data.parts : []);
        setOtherListableParts(
          Array.isArray(data.other_parts) ? data.other_parts : [],
        );
        setPartsCount(Number(data.parts_count || 0));
        const tp = Math.max(1, Number(data.parts_total_pages) || 1);
        setPartsTotalPages(tp);
        const srvPage = Math.max(
          1,
          Math.min(tp, Number(data.parts_page) || partsPage),
        );
        setPartsPage((prev) => (prev !== srvPage ? srvPage : prev));
        setInactiveParts(
          Array.isArray(data.inactive_parts) ? data.inactive_parts : [],
        );
        setActivePhoto(0);
        lastLoadedVehicleIdRef.current = idStr;
      } catch (e) {
        if (!cancelled && e instanceof ApiError) {
          if (isPartsOnlyRefetch) {
            toast.error(e.message);
          } else {
            setLoadError(e.message);
          }
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
          setPartsRefreshing(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, partsPage, partsSearch, toast]);

  // Load similar cars once vehicle is known
  useEffect(() => {
    if (!vehicle?.make || !vehicle?.model) return;
    let cancelled = false;
    (async () => {
      try {
        const data = await apiFetch("/browse/cars/assist/", {
          auth: false,
          method: "POST",
          body: JSON.stringify({
            buyer_year: vehicle.year,
            buyer_make: vehicle.make,
            buyer_model: vehicle.model,
            part_need: "",
            buyer_zip: readSavedZip(),
          }),
        });
        if (cancelled) return;
        const donors = Array.isArray(data.potential_cars)
          ? data.potential_cars
          : [];
        // Exclude the current vehicle
        setSimilarCars(
          donors.filter((c) => String(c.vehicle_id) !== String(id)).slice(0, 6),
        );
      } catch {
        /* silent */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [vehicle, id]);

  // Auto-build message text when vehicle or selected parts change
  useEffect(() => {
    if (!vehicle || msgManuallyEdited.current) return;
    const vName = [vehicle.year, vehicle.make, vehicle.model]
      .filter(Boolean)
      .join(" ");
    setMsgText(
      selectedMsgParts.length > 0
        ? `Hi, I'm looking for ${selectedMsgParts.join(", ")} from your ${vName}. Are these available?`
        : `Hi, I'm interested in parts from your ${vName}. Are any parts available?`,
    );
  }, [vehicle, selectedMsgParts]); // eslint-disable-line react-hooks/exhaustive-deps

  const gallery = vehicle?.photo_urls?.length ? vehicle.photo_urls : [];
  const mainSrc =
    gallery[activePhoto]?.url || vehicle?.primary_photo_url || gallery[0]?.url;

  function prevPhoto() {
    setActivePhoto((i) => (i - 1 + gallery.length) % gallery.length);
  }
  function nextPhoto() {
    setActivePhoto((i) => (i + 1) % gallery.length);
  }

  const getShippingMode = useCallback(
    (partId) => shippingByPart[partId] || "standard",
    [shippingByPart],
  );
  const zipOk = Boolean(buyerZip.trim());

  useEffect(() => {
    if (!partModal) return;
    const opts = partModal.shipping_preview?.shipping_options || [];
    const codes = new Set(opts.map((o) => o.code));
    let m = shippingByPart[partModal.id] || "standard";
    if (!codes.has(m) && opts[0]) m = opts[0].code;
    setModalShipMode(m);
  }, [partModal, shippingByPart]);

  async function addToCart(partId, mode, buyerNotes = "") {
    if (!user) return;
    try {
      await apiFetch("/cart/", {
        method: "POST",
        body: JSON.stringify({
          vehicle_part_id: partId,
          quantity: 1,
          shipping_mode: mode,
          buyer_zip: buyerZip.trim(),
          ...(buyerNotes.trim() ? { buyer_notes: buyerNotes.trim() } : {}),
        }),
      });
      toast.success("Added to cart.");
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    }
  }

  async function sendMessage(e) {
    e.preventDefault();
    if (!msgText.trim()) return;
    if (!user) {
      router.push(`/login?next=/browse/vehicles/${id}`);
      return;
    }
    const targetPartId = parts[0]?.id ?? otherListableParts[0]?.id;
    if (!targetPartId) return;
    setMsgSending(true);
    try {
      await apiFetch("/messages/start/", {
        method: "POST",
        body: JSON.stringify({
          vehicle_part_id: targetPartId,
          message: msgText.trim(),
        }),
      });
      setMsgSent(true);
      toast.success("Message sent.");
    } catch (e2) {
      toast.error(
        e2 instanceof ApiError
          ? e2.message
          : "Failed to send. Please try again.",
      );
    } finally {
      setMsgSending(false);
    }
  }

  // ─── Loading / Error states ───────────────────────────────────────────────
  if (loading) {
    return (
      <div
        className="mx-auto max-w-5xl px-4 py-16 text-center"
        style={{ color: "var(--text-secondary)" }}
      >
        Loading vehicle…
      </div>
    );
  }
  if (loadError || !vehicle) {
    return (
      <div className="mx-auto max-w-lg px-4 py-16 text-center">
        <p style={{ color: "var(--text-primary)" }}>
          {loadError || "Vehicle not found."}
        </p>
        <Link
          href="/browse"
          className="mt-6 inline-block font-medium hover:underline"
          style={{ color: "var(--accent)" }}
        >
          ← Browse
        </Link>
      </div>
    );
  }

  const v = vehicle;
  const headline = [v.year, v.make, v.model].filter(Boolean).join(" ");
  const mileageBit = v.mileage_unavailable
    ? "Mileage unavailable"
    : v.odometer_miles != null
      ? `${Number(v.odometer_miles).toLocaleString()} mi`
      : null;
  const specLine = [
    v.engine,
    v.transmission,
    v.drivetrain,
    v.body_style,
    v.color,
    mileageBit,
  ].filter(Boolean);

  const filteredInactive = inactiveQ.trim()
    ? inactiveParts.filter((p) =>
        p.label.toLowerCase().includes(inactiveQ.trim().toLowerCase()),
      )
    : inactiveParts;

  const partsPagerEntries = browseVehiclePartsPaginationEntries(
    partsTotalPages,
    partsPage - 1,
  );
  const partsRangeLabel =
    partsCount === 0
      ? "0 parts"
      : `Showing ${(partsPage - 1) * PARTS_PAGE_SIZE + 1}–${Math.min(partsPage * PARTS_PAGE_SIZE, partsCount)} of ${partsCount}`;
  const partsPaginationInner =
    partsTotalPages > 1 ? (
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:justify-center sm:gap-3">
        <span
          className="text-center text-xs"
          style={{ color: "var(--text-secondary)" }}
        >
          {partsRangeLabel}
        </span>
        <div className="flex flex-wrap items-center justify-center gap-1">
          <button
            type="button"
            onClick={() => setPartsPage((p) => Math.max(1, p - 1))}
            disabled={partsPage <= 1}
            className="rounded-lg border px-3 py-1.5 text-sm font-medium transition-all disabled:opacity-40"
            style={{
              borderColor: "var(--border)",
              background: "var(--bg-elevated)",
              color: "var(--text-primary)",
            }}
          >
            ← Prev
          </button>
          {partsPagerEntries.map((entry, idx) =>
            entry === "ellipsis" ? (
              <span
                key={`e-${idx}`}
                className="px-1.5 py-1.5 text-sm font-medium tracking-wide"
                style={{ color: "var(--text-muted)" }}
                aria-hidden
              >
                …
              </span>
            ) : (
              <button
                key={entry}
                type="button"
                onClick={() => setPartsPage(entry + 1)}
                className="min-w-[2.25rem] rounded-lg border px-2.5 py-1.5 text-sm font-medium transition-all"
                style={
                  entry === partsPage - 1
                    ? {
                        borderColor: "var(--accent-border-strong)",
                        background: "var(--accent-muted)",
                        color: "var(--accent)",
                      }
                    : {
                        borderColor: "var(--border)",
                        background: "var(--bg-elevated)",
                        color: "var(--text-secondary)",
                      }
                }
              >
                {entry + 1}
              </button>
            ),
          )}
          <button
            type="button"
            onClick={() =>
              setPartsPage((p) => Math.min(partsTotalPages, p + 1))
            }
            disabled={partsPage >= partsTotalPages}
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
      </div>
    ) : null;

  return (
    <div
      className="mx-auto min-h-screen max-w-5xl px-4 pb-16 pt-6 sm:px-6"
      style={{ background: "var(--bg-base)", color: "var(--text-primary)" }}
    >
      {/* Breadcrumb */}
      <nav className="mb-6 text-sm" style={{ color: "var(--text-secondary)" }}>
        <Link
          href="/browse"
          className="font-medium hover:underline"
          style={{ color: "var(--accent)" }}
        >
          ← Browse
        </Link>
        <span className="mx-2">·</span>
        <span style={{ color: "var(--text-primary)" }}>{headline}</span>
      </nav>

      {/* ── Vehicle header ──────────────────────────────────────────────────── */}
      <div className="grid gap-8 lg:grid-cols-2">
        {/* ── Gallery (slider) ─────────────────────────────────────────────── */}
        <div>
          {/* Main image with arrows */}
          <div
            className="relative aspect-[4/3] overflow-hidden rounded-2xl border select-none"
            style={{
              borderColor: "var(--border)",
              background: "var(--bg-surface)",
            }}
            onTouchStart={(e) => {
              touchStartX.current = e.touches[0].clientX;
            }}
            onTouchEnd={(e) => {
              if (touchStartX.current == null) return;
              const dx = e.changedTouches[0].clientX - touchStartX.current;
              touchStartX.current = null;
              if (gallery.length < 2) return;
              if (Math.abs(dx) > 30) dx < 0 ? nextPhoto() : prevPhoto();
            }}
          >
            {mainSrc ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={mainSrc}
                alt={headline}
                className="h-full w-full object-cover"
              />
            ) : (
              <div
                className="flex h-full w-full items-center justify-center text-sm"
                style={{ color: "var(--text-muted)" }}
              >
                No photos yet
              </div>
            )}

            {/* Photo counter */}
            {gallery.length > 1 && (
              <div className="absolute bottom-3 right-3 rounded-full bg-black/50 px-2.5 py-1 text-xs font-medium text-white backdrop-blur-sm">
                {activePhoto + 1} / {gallery.length}
              </div>
            )}

            {/* Arrows */}
            {gallery.length > 1 && (
              <>
                <button
                  type="button"
                  onClick={prevPhoto}
                  aria-label="Previous photo"
                  className="absolute left-2 top-1/2 -translate-y-1/2 rounded-full bg-black/40 p-2 text-white backdrop-blur-sm hover:bg-black/60"
                >
                  <svg
                    viewBox="0 0 16 16"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="h-4 w-4"
                  >
                    <path d="M10 3 5 8l5 5" />
                  </svg>
                </button>
                <button
                  type="button"
                  onClick={nextPhoto}
                  aria-label="Next photo"
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full bg-black/40 p-2 text-white backdrop-blur-sm hover:bg-black/60"
                >
                  <svg
                    viewBox="0 0 16 16"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="h-4 w-4"
                  >
                    <path d="M6 3l5 5-5 5" />
                  </svg>
                </button>
              </>
            )}
          </div>

          {/* Thumbnails strip */}
          {gallery.length > 1 && (
            <div className="mt-2 flex gap-2 overflow-x-auto pb-1">
              {gallery.map((p, idx) => (
                <button
                  key={p.id ?? idx}
                  type="button"
                  onClick={() => setActivePhoto(idx)}
                  className={`relative h-16 w-20 shrink-0 overflow-hidden rounded-lg border-2 transition ${
                    idx === activePhoto
                      ? "opacity-100"
                      : "border-transparent opacity-70 hover:opacity-100"
                  }`}
                  style={
                    idx === activePhoto
                      ? {
                          borderColor: "var(--accent)",
                          boxShadow:
                            "0 0 0 2px color-mix(in srgb, var(--accent) 22%, transparent)",
                        }
                      : undefined
                  }
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={p.url}
                    alt=""
                    className="h-full w-full object-cover"
                  />
                </button>
              ))}
            </div>
          )}
        </div>

        {/* ── Vehicle info ──────────────────────────────────────────────────── */}
        <div>
          <h1
            className="text-2xl font-bold tracking-tight sm:text-3xl"
            style={{ color: "var(--text-primary)" }}
          >
            {headline}
          </h1>
          {v.trim ? (
            <p
              className="mt-1 text-base font-medium leading-snug"
              style={{ color: "var(--text-secondary)" }}
            >
              {v.trim}
            </p>
          ) : null}

          {/* Spec chips */}
          <div className="mt-3 flex flex-wrap gap-1.5">
            {v.color && (
              <span
                className="rounded-md border px-2 py-0.5 text-xs"
                style={{
                  borderColor: "var(--border)",
                  background: "var(--bg-surface)",
                  color: "var(--text-secondary)",
                }}
              >
                <b style={{ color: "var(--text-primary)" }}>Color</b> {v.color}
              </span>
            )}
            {v.engine && (
              <span
                className="rounded-md border px-2 py-0.5 text-xs"
                style={{
                  borderColor: "var(--border)",
                  background: "var(--bg-surface)",
                  color: "var(--text-secondary)",
                }}
              >
                <b style={{ color: "var(--text-primary)" }}>Engine</b>{" "}
                {v.engine}
              </span>
            )}
            {v.transmission && (
              <span
                className="rounded-md border px-2 py-0.5 text-xs"
                style={{
                  borderColor: "var(--border)",
                  background: "var(--bg-surface)",
                  color: "var(--text-secondary)",
                }}
              >
                <b style={{ color: "var(--text-primary)" }}>Trans.</b>{" "}
                {v.transmission}
              </span>
            )}
            {v.drivetrain && (
              <span
                className="rounded-md border px-2 py-0.5 text-xs"
                style={{
                  borderColor: "var(--border)",
                  background: "var(--bg-surface)",
                  color: "var(--text-primary)",
                }}
              >
                {v.drivetrain}
              </span>
            )}
            {(v.location_state || v.location_zip_masked) && (
              <span
                className="rounded-md border px-2 py-0.5 text-xs"
                style={{
                  borderColor: "var(--border)",
                  background: "var(--bg-surface)",
                  color: "var(--text-secondary)",
                }}
              >
                📍{" "}
                {[v.location_state, v.location_zip_masked]
                  .filter(Boolean)
                  .join(" ")}
              </span>
            )}
          </div>
          {v.vin_masked && (
            <p className="mt-2 text-xs" style={{ color: "var(--text-muted)" }}>
              VIN …{v.vin_masked}
            </p>
          )}

          {/* Seller */}
          <div
            className="mt-4 rounded-xl border p-4"
            style={{
              borderColor: "var(--border)",
              background: "var(--bg-surface)",
            }}
          >
            <p
              className="text-xs font-semibold uppercase tracking-wide"
              style={{ color: "var(--text-muted)" }}
            >
              Seller
            </p>
            <p
              className="mt-1 font-semibold"
              style={{ color: "var(--text-primary)" }}
            >
              {v.seller?.display_name}
            </p>
            <p
              className="mt-0.5 text-sm leading-relaxed"
              style={{ color: "var(--text-secondary)" }}
            >
              {v.seller?.trust_note}
            </p>
          </div>

          {/* Damage */}
          {v.has_damage ? (
            <div
              className="mt-4 rounded-xl border p-4"
              style={{
                borderColor:
                  "color-mix(in srgb, var(--danger) 35%, transparent)",
                background: "var(--danger-muted)",
              }}
            >
              <div className="flex items-center gap-2">
                <svg
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  className="h-4 w-4 shrink-0"
                  style={{ color: "var(--danger)" }}
                  aria-hidden
                >
                  <path
                    fillRule="evenodd"
                    d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495ZM10 5a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0v-3.5A.75.75 0 0 1 10 5Zm0 9a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z"
                    clipRule="evenodd"
                  />
                </svg>
                <p
                  className="text-sm font-semibold"
                  style={{ color: "var(--danger)" }}
                >
                  Seller reports damage
                </p>
              </div>
              {v.damage_items?.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {v.damage_items.map((item) => (
                    <span
                      key={item}
                      className="rounded-full border px-2.5 py-1 text-xs font-medium"
                      style={{
                        background: "var(--bg-elevated)",
                        borderColor:
                          "color-mix(in srgb, var(--danger) 28%, transparent)",
                        color: "var(--danger)",
                      }}
                    >
                      {item}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div
              className="mt-4 flex items-center gap-2 rounded-xl border px-4 py-3"
              style={{
                borderColor:
                  "color-mix(in srgb, var(--success) 35%, transparent)",
                background: "var(--success-muted)",
              }}
            >
              <svg
                viewBox="0 0 20 20"
                fill="currentColor"
                className="h-4 w-4 shrink-0"
                style={{ color: "var(--success)" }}
                aria-hidden
              >
                <path
                  fillRule="evenodd"
                  d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z"
                  clipRule="evenodd"
                />
              </svg>
              <p
                className="text-sm font-medium"
                style={{ color: "var(--success)" }}
              >
                No damage reported
              </p>
            </div>
          )}

          {/* Shipping guide link */}
          <div className="mt-4">
            <ShippingGuide />
          </div>
        </div>
      </div>

      {/* ── Parts section (Buy now — server search + pagination) ───────────── */}
      <section
        className="mt-12 border-t pt-10"
        style={{ borderColor: "var(--border-subtle)" }}
      >
        <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2
              className="text-lg font-semibold"
              style={{ color: "var(--text-primary)" }}
            >
              Buy now{" "}
              <span
                className="ml-1.5 text-sm font-normal tabular-nums"
                style={{ color: "var(--text-secondary)" }}
              >
                ({partsCount})
              </span>
            </h2>
            <p
              className="mt-1 text-sm leading-relaxed"
              style={{ color: "var(--text-secondary)" }}
            >
              Click any part for full details.
              {!zipOk && (
                <>
                  {" "}
                  Set your ZIP on the{" "}
                  <Link
                    href="/browse"
                    className="font-medium hover:underline"
                    style={{ color: "var(--accent)" }}
                  >
                    browse page
                  </Link>{" "}
                  for shipping estimates.
                </>
              )}
            </p>
          </div>
          <div className="w-full lg:max-w-xs">
            <label htmlFor="browse-veh-parts-q" className="sr-only">
              Search buy now parts
            </label>
            <input
              id="browse-veh-parts-q"
              type="search"
              value={partsSearchInput}
              onChange={(e) => setPartsSearchInput(e.target.value)}
              placeholder="Search buy now parts…"
              className="input-forge h-10 w-full rounded-lg"
              autoComplete="off"
            />
          </div>
        </div>

        <div className="relative min-h-[4.5rem]">
          {partsRefreshing ? (
            <div
              className="absolute inset-0 z-10 flex items-center justify-center gap-2 rounded-xl py-10 text-sm font-medium backdrop-blur-[2px]"
              style={{
                background:
                  "color-mix(in srgb, var(--bg-base) 82%, transparent)",
                color: "var(--text-secondary)",
              }}
              aria-live="polite"
              aria-busy="true"
            >
              <span
                className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current opacity-40 border-t-transparent"
                aria-hidden
              />
              Updating listings…
            </div>
          ) : null}
          <div
            className={
              partsRefreshing ? "pointer-events-none opacity-50" : undefined
            }
          >
            {parts.length > 0 ? (
              <div className="space-y-2">
                {parts.map((p) => (
                  <BrowsePartCard
                    key={p.id}
                    part={p}
                    messageHref={
                      user
                        ? `${messageBaseHref}?part=${encodeURIComponent(String(p.id))}&auto=1&msg=${encodeURIComponent(`Hi, I'm interested in ${p.label} from your ${headline}. Is it available?`)}`
                        : messageBaseHref
                    }
                    selectable={false}
                    onAddToCart={
                      user
                        ? (pid, mode, notes) => void addToCart(pid, mode, notes)
                        : undefined
                    }
                    shippingMode={getShippingMode(p.id)}
                    onShippingModeChange={(pid, mode) =>
                      setShippingByPart((prev) => ({ ...prev, [pid]: mode }))
                    }
                    buyerZipPresent={zipOk}
                    onCardClick={() => setPartModal(p)}
                  />
                ))}
              </div>
            ) : (
              <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
                {partsSearch
                  ? "No buy now listings match your search."
                  : "No parts listed for direct purchase yet — see other listings below or message the seller."}
              </p>
            )}

            {partsPaginationInner ? (
              <div
                className="mt-8 border-t pt-8"
                style={{ borderColor: "var(--border-subtle)" }}
              >
                {partsPaginationInner}
              </div>
            ) : null}
          </div>
        </div>
      </section>

      {/* ── Inactive / sold parts ──────────────────────────────────────────── */}
      {inactiveParts.length > 0 && (
        <section
          className="mt-8 border-t pt-8"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <h3
            className="text-base font-semibold"
            style={{ color: "var(--text-primary)" }}
          >
            Previously listed parts
            <span
              className="ml-1.5 text-sm font-normal tabular-nums"
              style={{ color: "var(--text-secondary)" }}
            >
              ({inactiveParts.length})
            </span>
          </h3>
          <p
            className="mt-1 text-sm"
            style={{ color: "var(--text-secondary)" }}
          >
            These parts were listed but are no longer available.
          </p>
          <div className="mt-3">
            <input
              type="text"
              value={inactiveQ}
              onChange={(e) => setInactiveQ(e.target.value)}
              placeholder="Search parts…"
              className="input-forge h-9 w-full max-w-xs rounded-lg"
            />
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {filteredInactive.map((p) => {
              const st = STATE_LABELS[p.state] || STATE_LABELS.unavailable;
              return (
                <span
                  key={p.id}
                  className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium"
                  style={st.chip}
                >
                  {p.label}
                  <span style={{ opacity: 0.88 }}>· {st.label}</span>
                </span>
              );
            })}
          </div>
        </section>
      )}

      {/* ── Message the seller ─────────────────────────────────────────────── */}
      {(parts.length > 0 || otherListableParts.length > 0) && (
        <section
          className="mt-10 border-t pt-8"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <h2
            className="text-lg font-semibold"
            style={{ color: "var(--text-primary)" }}
          >
            Message the seller
          </h2>
          <p
            className="mt-1 text-sm"
            style={{ color: "var(--text-secondary)" }}
          >
            Ask about availability, condition, or shipping.
          </p>

          {msgSent ? (
            <div
              className="mt-4 flex items-center gap-3 rounded-xl border px-4 py-4"
              style={{
                borderColor:
                  "color-mix(in srgb, var(--success) 35%, transparent)",
                background: "var(--success-muted)",
              }}
            >
              <svg
                viewBox="0 0 20 20"
                fill="currentColor"
                className="h-5 w-5 shrink-0"
                style={{ color: "var(--success)" }}
                aria-hidden
              >
                <path
                  fillRule="evenodd"
                  d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z"
                  clipRule="evenodd"
                />
              </svg>
              <div>
                <p className="font-medium" style={{ color: "var(--success)" }}>
                  Message sent!
                </p>
                <p
                  className="text-sm"
                  style={{ color: "var(--text-secondary)" }}
                >
                  Check your{" "}
                  <Link
                    href="/inbox"
                    className="font-medium underline"
                    style={{ color: "var(--accent)" }}
                  >
                    inbox
                  </Link>{" "}
                  for the reply.
                </p>
              </div>
            </div>
          ) : (
            <form onSubmit={sendMessage} className="mt-4 space-y-3">
              <div
                className="rounded-xl border p-3"
                style={{
                  borderColor: "var(--border)",
                  background: "var(--bg-surface)",
                }}
              >
                <PartsPickerMulti
                  selected={selectedMsgParts}
                  onChange={(p) => {
                    setSelectedMsgParts(p);
                    msgManuallyEdited.current = false;
                  }}
                  label="Which parts are you looking for?"
                />
              </div>
              <textarea
                value={msgText}
                onChange={(e) => {
                  setMsgText(e.target.value);
                  msgManuallyEdited.current = true;
                }}
                rows={4}
                placeholder="Type your message…"
                className="input-forge w-full resize-none rounded-xl px-4 py-3"
                style={{ minHeight: "6rem" }}
              />
              <div className="flex items-center justify-between">
                {!user && (
                  <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                    You will be asked to sign in before sending.
                  </p>
                )}
                <button
                  type="submit"
                  disabled={msgSending || !msgText.trim()}
                  className="btn-forge ml-auto inline-flex items-center gap-2 px-5 py-2.5 text-sm disabled:opacity-60"
                >
                  {msgSending ? (
                    <>
                      <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                      Sending…
                    </>
                  ) : (
                    <>
                      <svg
                        viewBox="0 0 20 20"
                        fill="currentColor"
                        className="h-4 w-4"
                        aria-hidden
                      >
                        <path d="M3.105 2.289a.75.75 0 0 0-.826.95l1.414 4.925A1.5 1.5 0 0 0 5.135 9.25h6.115a.75.75 0 0 1 0 1.5H5.135a1.5 1.5 0 0 0-1.442 1.086l-1.414 4.926a.75.75 0 0 0 .826.95 28.896 28.896 0 0 0 15.293-7.154.75.75 0 0 0 0-1.115A28.897 28.897 0 0 0 3.105 2.289Z" />
                      </svg>
                      Send message
                    </>
                  )}
                </button>
              </div>
            </form>
          )}
        </section>
      )}

      {/* ── Similar vehicles ───────────────────────────────────────────────── */}
      {similarCars.length > 0 && (
        <section
          className="mt-12 border-t pt-10"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <h2
            className="text-lg font-semibold"
            style={{ color: "var(--text-primary)" }}
          >
            Similar vehicles
          </h2>
          <p
            className="mt-1 text-sm"
            style={{ color: "var(--text-secondary)" }}
          >
            Other {v.year} {v.make} {v.model} donors on Partbridge.
          </p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {similarCars.map((c) => {
              const photos = c.photo_urls?.length
                ? c.photo_urls
                : c.primary_photo_url
                  ? [{ url: c.primary_photo_url }]
                  : [];
              const name = [c.year, c.make, c.model, c.trim]
                .filter(Boolean)
                .join(" ");
              return (
                <Link
                  key={c.vehicle_id}
                  href={`/browse/vehicles/${c.vehicle_id}`}
                  className="group overflow-hidden rounded-xl border transition hover:shadow-md"
                  style={{
                    borderColor: "var(--border)",
                    background: "var(--bg-elevated)",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor =
                      "var(--accent-border-soft)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = "var(--border)";
                  }}
                >
                  <div
                    className="aspect-[16/9] overflow-hidden"
                    style={{ background: "var(--bg-surface)" }}
                  >
                    {photos[0] ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={photos[0].url}
                        alt={name}
                        className="h-full w-full object-cover group-hover:scale-105 transition duration-300"
                      />
                    ) : (
                      <div
                        className="flex h-full w-full items-center justify-center text-sm"
                        style={{ color: "var(--text-muted)" }}
                      >
                        No photo
                      </div>
                    )}
                  </div>
                  <div className="p-3">
                    <p
                      className="text-sm font-semibold transition-colors group-hover:underline"
                      style={{ color: "var(--text-primary)" }}
                    >
                      {name}
                    </p>
                    <p
                      className="mt-0.5 text-xs"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      {[c.location_state, c.location_zip_masked]
                        .filter(Boolean)
                        .join(" ")}
                    </p>
                  </div>
                </Link>
              );
            })}
          </div>
        </section>
      )}

      {/* ── Buy-now part detail modal ──────────────────────────────────────── */}
      {partModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          role="dialog"
          aria-modal
        >
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setPartModal(null)}
          />
          <div
            className="relative z-10 max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl shadow-2xl"
            style={{ background: "var(--bg-elevated)" }}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between border-b px-5 py-4 gap-3"
              style={{ borderColor: "var(--border)" }}
            >
              <div className="min-w-0 flex-1">
                <h2
                  className="text-base font-semibold"
                  style={{ color: "var(--text-primary)" }}
                >
                  {partModal.label}
                </h2>
                <Link
                  href={`/browse/parts/${partModal.id}`}
                  className="mt-1 inline-block text-xs font-semibold"
                  style={{ color: "var(--primary)" }}
                >
                  Open full part page →
                </Link>
              </div>
              <button
                type="button"
                onClick={() => setPartModal(null)}
                className="rounded-lg p-1.5 transition-colors"
                style={{ color: "var(--text-muted)" }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "var(--bg-hover)";
                  e.currentTarget.style.color = "var(--text-primary)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "transparent";
                  e.currentTarget.style.color = "var(--text-muted)";
                }}
              >
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={1.75}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-5 w-5"
                >
                  <path d="M18 6 6 18M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="p-5">
              {/* Image */}
              {(partModal.card_image_url || partModal.image_urls?.[0]) && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={partModal.card_image_url || partModal.image_urls[0]}
                  alt={partModal.label}
                  className="mb-4 h-52 w-full rounded-xl object-cover"
                />
              )}

              {/* Price + badges */}
              <div className="flex flex-wrap items-center gap-2">
                {modalBuyPrice != null && (
                  <span
                    className="text-2xl font-bold tabular-nums"
                    style={{ color: "var(--primary)" }}
                  >
                    {modalShowOffer && modalListNum != null && (
                      <span
                        className="mr-2 text-base font-semibold line-through opacity-60"
                        style={{ color: "var(--text-muted)" }}
                      >
                        {new Intl.NumberFormat("en-US", {
                          style: "currency",
                          currency: "USD",
                        }).format(modalListNum)}
                      </span>
                    )}
                    {new Intl.NumberFormat("en-US", {
                      style: "currency",
                      currency: "USD",
                    }).format(modalBuyPrice)}
                  </span>
                )}
                {partModal.offer_expires_at && modalShowOffer && (
                  <span
                    className="rounded-full border px-2.5 py-0.5 text-xs font-medium"
                    style={{
                      borderColor: "var(--primary-border-soft)",
                      background: "var(--primary-muted)",
                      color: "var(--primary)",
                    }}
                  >
                    Limited offer · ends{" "}
                    {new Date(partModal.offer_expires_at).toLocaleString()}
                  </span>
                )}
                {partModal.condition_draft && (
                  <span
                    className="rounded-full border px-2.5 py-0.5 text-xs font-medium"
                    style={{
                      borderColor: "var(--border)",
                      background: "var(--bg-surface)",
                      color: "var(--text-secondary)",
                    }}
                  >
                    {partModal.condition_draft.replace(/_/g, " ")}
                  </span>
                )}
                {partModal.return_policy === "green" && (
                  <span
                    className="rounded-full border px-2.5 py-0.5 text-xs font-medium"
                    style={{
                      background: "var(--success-muted)",
                      borderColor:
                        "color-mix(in srgb, var(--success) 30%, transparent)",
                      color: "var(--success)",
                    }}
                  >
                    30-day buyer protection — full refund if not as described
                  </span>
                )}
                {partModal.return_policy === "yellow" && (
                  <span
                    className="rounded-full border px-2.5 py-0.5 text-xs font-medium"
                    style={{
                      background: "var(--warning-muted)",
                      borderColor:
                        "color-mix(in srgb, var(--warning) 35%, transparent)",
                      color: "var(--warning)",
                    }}
                  >
                    Partial returns — restocking fee may apply
                  </span>
                )}
                {partModal.return_policy === "red" && (
                  <span
                    className="rounded-full border px-2.5 py-0.5 text-xs font-medium"
                    style={{
                      background: "var(--danger-muted)",
                      borderColor:
                        "color-mix(in srgb, var(--danger) 30%, transparent)",
                      color: "var(--danger)",
                    }}
                  >
                    Final sale — no returns
                  </span>
                )}
              </div>

              {/* Description */}
              {partModal.description && (
                <p
                  className="mt-3 text-sm leading-relaxed"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {partModal.description}
                </p>
              )}

              {/* Donor vehicle */}
              <div
                className="mt-4 rounded-xl border p-3"
                style={{
                  borderColor: "var(--border)",
                  background: "var(--bg-surface)",
                }}
              >
                <p
                  className="text-xs font-semibold uppercase tracking-wide"
                  style={{ color: "var(--text-muted)" }}
                >
                  From this vehicle
                </p>
                <p
                  className="mt-1 text-sm font-medium"
                  style={{ color: "var(--text-primary)" }}
                >
                  {headline}
                </p>
                <p
                  className="text-xs"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {specLine.join(" · ")}
                </p>
              </div>

              {/* Shipping preview — selectable (matches list + checkout) */}
              {partModal.shipping_preview?.available &&
                partModal.shipping_preview.shipping_options?.length > 0 && (
                  <div className="mt-4">
                    <p
                      className="mb-2 text-xs font-semibold uppercase tracking-wide"
                      style={{ color: "var(--text-muted)" }}
                    >
                      Shipping options
                    </p>
                    <div className="flex flex-col gap-2">
                      {partModal.shipping_preview.shipping_options.map(
                        (opt) => (
                          <label
                            key={opt.code}
                            className="flex cursor-pointer items-center gap-3 rounded-xl border px-3 py-2.5 text-sm transition-colors"
                            style={
                              modalShipMode === opt.code
                                ? {
                                    borderColor: "var(--accent-border-strong)",
                                    background: "var(--accent-muted)",
                                  }
                                : {
                                    borderColor: "var(--border)",
                                    background: "var(--bg-elevated)",
                                  }
                            }
                            onMouseEnter={(e) => {
                              if (modalShipMode !== opt.code) {
                                e.currentTarget.style.borderColor =
                                  "var(--border-strong)";
                              }
                            }}
                            onMouseLeave={(e) => {
                              if (modalShipMode === opt.code) {
                                e.currentTarget.style.borderColor =
                                  "var(--accent-border-strong)";
                                e.currentTarget.style.background =
                                  "var(--accent-muted)";
                              } else {
                                e.currentTarget.style.borderColor =
                                  "var(--border)";
                                e.currentTarget.style.background =
                                  "var(--bg-elevated)";
                              }
                            }}
                          >
                            <input
                              type="radio"
                              name="modal-shipping"
                              className="h-4 w-4 shrink-0"
                              style={{ accentColor: "var(--accent)" }}
                              checked={modalShipMode === opt.code}
                              onChange={() => {
                                setModalShipMode(opt.code);
                                setShippingByPart((prev) => ({
                                  ...prev,
                                  [partModal.id]: opt.code,
                                }));
                              }}
                            />
                            <span className="min-w-0 flex-1">
                              <span
                                className="font-medium"
                                style={{ color: "var(--text-primary)" }}
                              >
                                {opt.label}
                              </span>
                              <span
                                className="ml-2 tabular-nums"
                                style={{ color: "var(--text-secondary)" }}
                              >
                                {Number(opt.usd) === 0 ? "Free" : `$${opt.usd}`}
                              </span>
                              {opt.note ? (
                                <span
                                  className="mt-0.5 block text-xs"
                                  style={{ color: "var(--text-muted)" }}
                                >
                                  {opt.note}
                                </span>
                              ) : null}
                            </span>
                          </label>
                        ),
                      )}
                    </div>
                  </div>
                )}
              {!zipOk && (
                <p
                  className="mt-2 text-xs font-medium"
                  style={{ color: "var(--warning)" }}
                >
                  Set your ZIP on the browse page to see exact shipping prices.
                </p>
              )}

              {/* Actions */}
              <div className="mt-5 flex gap-2">
                <Link
                  href={
                    user
                      ? `${messageBaseHref}?part=${encodeURIComponent(String(partModal.id))}&auto=1&msg=${encodeURIComponent(`Hi, I'm interested in ${partModal.label}. Is it still available?`)}`
                      : messageBaseHref
                  }
                  className="btn-ghost flex-1 justify-center py-2.5 text-sm"
                >
                  Message
                </Link>
                {modalCanBuyNow && (
                  <Link
                    href={`/checkout?part=${encodeURIComponent(String(partModal.id))}&shipping=${encodeURIComponent(modalShipMode)}`}
                    className="btn-forge flex-1 justify-center py-2.5 text-center text-sm"
                  >
                    Buy Now
                  </Link>
                )}
                {!modalCanBuyNow && modalListingEff === "sold" && (
                    <span
                      className="flex flex-1 items-center justify-center rounded-lg py-2.5 text-center text-sm font-semibold"
                      style={{
                        background: "var(--bg-surface)",
                        border: "1px solid var(--border)",
                        color: "var(--text-muted)",
                      }}
                    >
                      Sold
                    </span>
                  )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
