"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { useBuyerCar } from "@/context/car-context";
import { ThemeToggle } from "@/components/ThemeToggle";
import {
  getMakes,
  getModels,
  getGenerations,
  getModifications,
} from "@/lib/api";
import FeaturedCategories from "@/components/home/FeaturedCategories";
import MakeStrip from "@/components/home/MakeStrip";
import RecentParts from "@/components/home/RecentParts";

/* ─── Scroll fade-in ────────────────────────────────────────────────────────── */

function useInView(threshold = 0.15) {
  const ref = useRef(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          setInView(true);
          obs.disconnect();
        }
      },
      { threshold },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);
  return [ref, inView];
}

function Reveal({ children, delay = 0, className = "", direction = "up" }) {
  const [ref, inView] = useInView();
  const y = direction === "up" ? 20 : direction === "down" ? -20 : 0;
  const x = direction === "right" ? -20 : direction === "left" ? 20 : 0;
  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: inView ? 1 : 0,
        transform: inView ? "translate(0,0)" : `translate(${x}px,${y}px)`,
        transition: `opacity 0.6s cubic-bezier(0.22,1,0.36,1) ${delay}ms, transform 0.6s cubic-bezier(0.22,1,0.36,1) ${delay}ms`,
      }}
    >
      {children}
    </div>
  );
}

/* ─── Icons ─────────────────────────────────────────────────────────────────── */

const S = ({ c, style, children }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={1.75}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={c}
    style={style}
    aria-hidden
  >
    {children}
  </svg>
);
const IcMenu = ({ c }) => (
  <S c={c}>
    <path d="M4 6h16M4 12h16M4 18h16" />
  </S>
);
const IcX = ({ c }) => (
  <S c={c}>
    <path d="M18 6 6 18m0-12 12 12" />
  </S>
);
const IcCheck = ({ c, style }) => (
  <S c={c} style={style}>
    <polyline points="20 6 9 17 4 12" />
  </S>
);

/* ─── Demo frame helpers ────────────────────────────────────────────────────── */

const DEMO_STEPS = [
  "List vehicle",
  "Parts priced",
  "Buyer finds it",
  "You get paid",
];

function BrowserShell({ url = "lookmypart.com", children }) {
  return (
    <div
      style={{
        background: "var(--bg-base)",
        border: "1px solid var(--border)",
        borderRadius: 16,
        overflow: "hidden",
        boxShadow:
          "0 24px 64px -12px rgba(0,0,0,0.22), 0 8px 20px -4px rgba(0,0,0,0.08)",
      }}
    >
      <div
        style={{
          background: "var(--bg-surface)",
          borderBottom: "1px solid var(--border)",
          padding: "9px 14px",
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <div style={{ display: "flex", gap: 5 }}>
          {["#FF5F57", "#FFBD2E", "#28C840"].map((c) => (
            <div
              key={c}
              style={{
                width: 9,
                height: 9,
                borderRadius: "50%",
                background: c,
              }}
            />
          ))}
        </div>
        <div
          style={{
            flex: 1,
            marginLeft: 4,
            background: "var(--bg-elevated)",
            borderRadius: 6,
            padding: "3px 10px",
            fontSize: 11,
            color: "var(--text-muted)",
            fontFamily: "var(--ff-mono)",
            textAlign: "center",
          }}
        >
          {url}
        </div>
      </div>
      {children}
    </div>
  );
}

/* ─── Demo frames ───────────────────────────────────────────────────────────── */

function FrameListVehicle({ onNext }) {
  return (
    <div style={{ padding: "20px 18px" }}>
      <div
        style={{
          fontSize: 11,
          fontFamily: "var(--ff-body)",
          fontWeight: 600,
          color: "var(--text-muted)",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          marginBottom: 14,
        }}
      >
        Add your vehicle
      </div>
      <div
        style={{
          background: "var(--bg-surface)",
          border: "1px solid var(--border)",
          borderRadius: 10,
          padding: "11px 14px",
          marginBottom: 8,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <span
          style={{
            fontSize: 12,
            fontFamily: "var(--ff-mono)",
            color: "var(--text-primary)",
          }}
        >
          1FTFW1ET5JFA12345
        </span>
        <span
          style={{
            fontSize: 11,
            color: "var(--success)",
            fontFamily: "var(--ff-body)",
            fontWeight: 600,
          }}
        >
          ✓ Decoded
        </span>
      </div>
      <div
        style={{
          background: "var(--primary-muted)",
          border: "1px solid var(--primary-border-soft)",
          borderRadius: 10,
          padding: "12px 14px",
          marginBottom: 6,
        }}
      >
        <div
          style={{
            fontSize: 15,
            fontWeight: 700,
            color: "var(--text-primary)",
            fontFamily: "var(--ff-body)",
            marginBottom: 2,
          }}
        >
          2018 Ford F-150 XLT
        </div>
        <div
          style={{
            fontSize: 12,
            color: "var(--text-muted)",
            fontFamily: "var(--ff-body)",
          }}
        >
          5.0L V8 · SuperCrew · 4WD
        </div>
      </div>
      <div
        style={{
          fontSize: 11,
          color: "var(--primary)",
          fontFamily: "var(--ff-body)",
          marginBottom: 14,
          paddingLeft: 2,
        }}
      >
        → 240 parts will be listed automatically with exact OEM data
      </div>
      <button
        onClick={onNext}
        style={{
          width: "100%",
          background: "var(--primary)",
          borderRadius: 8,
          padding: "11px 0",
          textAlign: "center",
          fontSize: 13,
          fontWeight: 600,
          color: "#fff",
          fontFamily: "var(--ff-body)",
          border: "none",
          cursor: "pointer",
        }}
      >
        List this vehicle →
      </button>
    </div>
  );
}

function FramePartsPriced({ onNext }) {
  const parts = [
    { name: "Engine Assembly", pn: "BL3Z-6006-A", range: "$900 – $1,500" },
    { name: "Alternator", pn: "DL3Z-10346-A", range: "$60 – $110" },
    { name: "Front Bumper", pn: "FL3Z-17D957-A", range: "$80 – $180" },
    { name: "Side Mirror (L)", pn: "FL3Z-17682-A", range: "$35 – $75" },
  ];
  return (
    <div style={{ padding: "20px 18px" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: 12,
        }}
      >
        <div>
          <div
            style={{
              fontSize: 11,
              fontFamily: "var(--ff-body)",
              fontWeight: 600,
              color: "var(--text-muted)",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
            }}
          >
            Listed in minutes
          </div>
          <div
            style={{
              fontSize: 13,
              color: "var(--primary)",
              fontWeight: 700,
              fontFamily: "var(--ff-body)",
            }}
          >
            240 parts ready to list
          </div>
        </div>
        <span
          style={{
            fontSize: 10,
            color: "var(--success)",
            fontFamily: "var(--ff-body)",
            fontWeight: 600,
            background: "rgba(34,197,94,0.1)",
            border: "1px solid rgba(34,197,94,0.2)",
            borderRadius: 6,
            padding: "3px 8px",
            whiteSpace: "nowrap",
          }}
        >
          All automatic
        </span>
      </div>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 5,
          marginBottom: 12,
        }}
      >
        {parts.map((p) => (
          <div
            key={p.name}
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: "8px 11px",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <span
                style={{
                  fontSize: 13,
                  color: "var(--text-primary)",
                  fontFamily: "var(--ff-body)",
                  fontWeight: 500,
                }}
              >
                {p.name}
              </span>
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  color: "var(--primary)",
                  fontFamily: "var(--ff-mono)",
                }}
              >
                {p.range}
              </span>
            </div>
            <div
              style={{
                fontSize: 10,
                color: "var(--text-disabled)",
                fontFamily: "var(--ff-mono)",
                marginTop: 1,
              }}
            >
              Part# {p.pn}
            </div>
          </div>
        ))}
      </div>
      <button
        onClick={onNext}
        style={{
          width: "100%",
          background: "var(--primary)",
          borderRadius: 8,
          padding: "10px 0",
          textAlign: "center",
          fontSize: 13,
          fontWeight: 600,
          color: "#fff",
          fontFamily: "var(--ff-body)",
          border: "none",
          cursor: "pointer",
        }}
      >
        Set prices &amp; publish →
      </button>
    </div>
  );
}

function FrameBuyerFinds({ onNext }) {
  return (
    <div style={{ padding: "20px 18px" }}>
      <div
        style={{
          background: "var(--bg-surface)",
          border: "1px solid var(--primary)",
          borderRadius: 10,
          padding: "9px 12px",
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 14,
          boxShadow: "0 0 0 3px var(--primary-muted)",
        }}
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.75}
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{
            width: 13,
            height: 13,
            color: "var(--text-muted)",
            flexShrink: 0,
          }}
          aria-hidden
        >
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.35-4.35" />
        </svg>
        <span
          style={{
            fontSize: 13,
            color: "var(--text-primary)",
            fontFamily: "var(--ff-body)",
          }}
        >
          Alternator — 2018 Ford F-150
        </span>
      </div>
      <div
        style={{
          background: "var(--bg-surface)",
          border: "1px solid var(--border)",
          borderRadius: 12,
          overflow: "hidden",
          marginBottom: 12,
        }}
      >
        <div
          style={{
            background: "rgba(34,197,94,0.08)",
            borderBottom: "1px solid rgba(34,197,94,0.18)",
            padding: "7px 12px",
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2.2}
            strokeLinecap="round"
            strokeLinejoin="round"
            style={{
              width: 12,
              height: 12,
              color: "var(--success)",
              flexShrink: 0,
            }}
            aria-hidden
          >
            <polyline points="20 6 9 17 4 12" />
          </svg>
          <span
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: "var(--success)",
              fontFamily: "var(--ff-body)",
            }}
          >
            Fits your 2018 Ford F-150 XLT · 5.0L V8
          </span>
        </div>
        <div style={{ display: "flex", gap: 12, padding: "12px" }}>
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: 8,
              background: "var(--bg-elevated)",
              border: "1px solid var(--border)",
              flexShrink: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
              style={{ width: 18, height: 18, color: "var(--text-disabled)" }}
              aria-hidden
            >
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <path d="M21 15l-5-5L5 21" />
            </svg>
          </div>
          <div style={{ flex: 1 }}>
            <div
              style={{
                fontSize: 13,
                fontWeight: 600,
                color: "var(--text-primary)",
                fontFamily: "var(--ff-body)",
              }}
            >
              Alternator
            </div>
            <div
              style={{
                fontSize: 10,
                color: "var(--text-disabled)",
                fontFamily: "var(--ff-mono)",
                marginBottom: 8,
              }}
            >
              Part# DL3Z-10346-A · Condition: Good
            </div>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <span
                style={{
                  fontSize: 17,
                  fontWeight: 700,
                  color: "var(--primary)",
                  fontFamily: "var(--ff-body)",
                }}
              >
                $95
              </span>
              <button
                onClick={onNext}
                style={{
                  background: "var(--primary)",
                  borderRadius: 6,
                  padding: "5px 14px",
                  fontSize: 12,
                  fontWeight: 600,
                  color: "#fff",
                  fontFamily: "var(--ff-body)",
                  border: "none",
                  cursor: "pointer",
                }}
              >
                Buy Now →
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function FrameSold() {
  return (
    <div
      style={{
        padding: "24px 18px",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: 220,
      }}
    >
      <div
        style={{
          width: 52,
          height: 52,
          borderRadius: "50%",
          background: "rgba(34,197,94,0.12)",
          border: "1px solid rgba(34,197,94,0.28)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: 12,
        }}
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2.2}
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{ width: 22, height: 22, color: "var(--success)" }}
          aria-hidden
        >
          <polyline points="20 6 9 17 4 12" />
        </svg>
      </div>
      <div
        style={{
          fontSize: 16,
          fontWeight: 700,
          color: "var(--text-primary)",
          fontFamily: "var(--ff-body)",
          marginBottom: 4,
        }}
      >
        Alternator sold
      </div>
      <div
        style={{
          fontSize: 32,
          fontWeight: 800,
          color: "var(--primary)",
          fontFamily: "var(--ff-body)",
          letterSpacing: "-0.03em",
          marginBottom: 20,
        }}
      >
        +$95.00
      </div>
      <div
        style={{
          width: "100%",
          background: "var(--bg-surface)",
          border: "1px solid var(--border)",
          borderRadius: 10,
          padding: "12px 14px",
          display: "flex",
          flexDirection: "column",
          gap: 8,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span
            style={{
              fontSize: 12,
              color: "var(--text-muted)",
              fontFamily: "var(--ff-body)",
            }}
          >
            Balance
          </span>
          <span
            style={{
              fontSize: 12,
              fontWeight: 600,
              color: "var(--text-primary)",
              fontFamily: "var(--ff-mono)",
            }}
          >
            $95.00
          </span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span
            style={{
              fontSize: 12,
              color: "var(--text-muted)",
              fontFamily: "var(--ff-body)",
            }}
          >
            Shipping label
          </span>
          <span
            style={{
              fontSize: 12,
              color: "var(--success)",
              fontFamily: "var(--ff-body)",
            }}
          >
            Generated ✓
          </span>
        </div>
      </div>
    </div>
  );
}

/* ─── Scroll-driven demo ────────────────────────────────────────────────────── */

function ScrollDemo() {
  const containerRef = useRef(null);
  const [frame, setFrame] = useState(0);
  const [fading, setFading] = useState(false);
  const lastFrameRef = useRef(0);
  const isFadingRef = useRef(false);

  useEffect(() => {
    const handleScroll = () => {
      const el = containerRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const totalScroll = el.offsetHeight - window.innerHeight;
      if (totalScroll <= 0) return;
      const scrolled = Math.max(0, Math.min(totalScroll, -rect.top));
      const progress = scrolled / totalScroll;
      const newFrame = Math.min(
        DEMO_STEPS.length - 1,
        Math.floor(progress * DEMO_STEPS.length),
      );
      if (newFrame !== lastFrameRef.current && !isFadingRef.current) {
        lastFrameRef.current = newFrame;
        isFadingRef.current = true;
        setFading(true);
        setTimeout(() => {
          setFrame(newFrame);
          setFading(false);
          isFadingRef.current = false;
        }, 380);
      }
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  function scrollToFrame(n) {
    const el = containerRef.current;
    if (!el) return;
    const totalScroll = el.offsetHeight - window.innerHeight;
    window.scrollTo({
      top: el.offsetTop + ((n + 0.15) / DEMO_STEPS.length) * totalScroll,
      behavior: "smooth",
    });
  }

  const advance = () =>
    scrollToFrame(Math.min(DEMO_STEPS.length - 1, lastFrameRef.current + 1));

  return (
    <div ref={containerRef} style={{ height: "350vh", position: "relative" }}>
      <div
        style={{
          position: "sticky",
          top: 0,
          height: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "flex-start",
          paddingTop: "clamp(48px, 9vh, 88px)",
          background: "var(--bg-base)",
          padding: "clamp(48px, 9vh, 88px) 16px 20px",
        }}
      >
        {/* Step indicators */}
        <div
          style={{
            display: "flex",
            gap: 20,
            marginBottom: 20,
            flexWrap: "wrap",
            justifyContent: "center",
          }}
        >
          {DEMO_STEPS.map((label, i) => (
            <button
              key={i}
              onClick={() => scrollToFrame(i)}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 5,
                background: "none",
                border: "none",
                cursor: "pointer",
                padding: 0,
              }}
            >
              <div
                style={{
                  width: 26,
                  height: 26,
                  borderRadius: "50%",
                  background:
                    i === frame ? "var(--primary)" : "var(--bg-elevated)",
                  border:
                    i < frame
                      ? "2px solid var(--primary)"
                      : i === frame
                        ? "none"
                        : "1px solid var(--border)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  transition: "all 0.4s cubic-bezier(0.22,1,0.36,1)",
                  fontSize: 10,
                  fontWeight: 700,
                  color:
                    i === frame
                      ? "#fff"
                      : i < frame
                        ? "var(--primary)"
                        : "var(--text-disabled)",
                  fontFamily: "var(--ff-mono)",
                }}
              >
                {i < frame ? (
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2.5}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    style={{ width: 11, height: 11 }}
                    aria-hidden
                  >
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : (
                  i + 1
                )}
              </div>
              <span
                style={{
                  fontSize: 10,
                  fontFamily: "var(--ff-body)",
                  whiteSpace: "nowrap",
                  color:
                    i === frame
                      ? "var(--text-primary)"
                      : i < frame
                        ? "var(--text-muted)"
                        : "var(--text-disabled)",
                  fontWeight: i === frame ? 600 : 400,
                  transition: "color 0.35s",
                }}
              >
                {label}
              </span>
            </button>
          ))}
        </div>

        {/* Card */}
        <div style={{ width: "100%", maxWidth: 420 }}>
          <BrowserShell>
            <div
              style={{
                minHeight: 240,
                opacity: fading ? 0 : 1,
                transition: "opacity 0.38s ease",
              }}
            >
              {frame === 0 && <FrameListVehicle onNext={advance} />}
              {frame === 1 && <FramePartsPriced onNext={advance} />}
              {frame === 2 && <FrameBuyerFinds onNext={advance} />}
              {frame === 3 && <FrameSold />}
            </div>
          </BrowserShell>
        </div>

        {/* Progress */}
        <div
          style={{
            marginTop: 16,
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          <span
            style={{
              fontSize: 10,
              color: "var(--text-disabled)",
              fontFamily: "var(--ff-body)",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
            }}
          >
            Scroll
          </span>
          <div
            style={{
              height: 2,
              width: 64,
              background: "var(--border)",
              borderRadius: 1,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                height: "100%",
                width: `${((frame + 1) / DEMO_STEPS.length) * 100}%`,
                background: "var(--primary)",
                borderRadius: 1,
                transition: "width 0.4s cubic-bezier(0.22,1,0.36,1)",
              }}
            />
          </div>
          <span
            style={{
              fontSize: 10,
              color: "var(--text-disabled)",
              fontFamily: "var(--ff-mono)",
            }}
          >
            {frame + 1} / {DEMO_STEPS.length}
          </span>
        </div>
      </div>
    </div>
  );
}

/* ─── Buyer car wizard ──────────────────────────────────────────────────────── */

function BuyerCarWizard({ onSubmit }) {
  const [step, setStep] = useState(0);
  const [fading, setFading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  const [makes, setMakes] = useState([]);
  const [models, setModels] = useState([]);
  const [generations, setGenerations] = useState([]);
  const [modifications, setModifications] = useState([]);

  const [sel, setSel] = useState({
    makeId: null,
    makeName: "",
    modelId: null,
    modelName: "",
    generationId: null,
    genLabel: "",
    yearMin: 1970,
    yearMax: new Date().getFullYear(),
    year: null,
  });

  useEffect(() => {
    getMakes()
      .then((d) => setMakes(Array.isArray(d) ? d : d?.results || []))
      .finally(() => setLoading(false));
  }, []);

  function fade(fn) {
    setSearch("");
    setFading(true);
    setTimeout(() => {
      fn();
      setFading(false);
    }, 180);
  }

  function goBack() {
    const prev = step - 1;
    setLoading(false);
    if (prev === 0) {
      setSel((s) => ({
        ...s,
        modelId: null,
        modelName: "",
        generationId: null,
        genLabel: "",
        year: null,
      }));
      setModels([]);
      setGenerations([]);
      setModifications([]);
    } else if (prev === 1) {
      setSel((s) => ({ ...s, generationId: null, genLabel: "", year: null }));
      setGenerations([]);
      setModifications([]);
    } else if (prev === 2) {
      setSel((s) => ({ ...s, year: null }));
      setModifications([]);
    }
    fade(() => setStep(prev));
  }

  function pickMake(m) {
    setSel((s) => ({
      ...s,
      makeId: m.id,
      makeName: m.name,
      modelId: null,
      modelName: "",
      generationId: null,
      genLabel: "",
      year: null,
    }));
    setLoading(true);
    getModels(m.id)
      .then((d) => setModels(Array.isArray(d) ? d : d?.results || []))
      .finally(() => setLoading(false));

    fade(() => setStep(1));
  }

  function pickModel(m) {
    setSel((s) => ({
      ...s,
      modelId: m.id,
      modelName: m.name,
      generationId: null,
      genLabel: "",
      year: null,
    }));
    setLoading(true);
    getGenerations(m.id)
      .then((d) => setGenerations(Array.isArray(d) ? d : d?.results || []))
      .finally(() => setLoading(false));
    fade(() => setStep(2));
  }

  function pickGeneration(g) {
    const yearMin = g.production_start
      ? new Date(g.production_start).getFullYear()
      : 1970;
    const yearMax = g.production_end
      ? new Date(g.production_end).getFullYear()
      : new Date().getFullYear();
    setSel((s) => ({
      ...s,
      generationId: g.id,
      genLabel: g.display_label || g.name,
      yearMin,
      yearMax,
      year: null,
    }));
    setLoading(true);
    getModifications(g.id)
      .then((d) => setModifications(Array.isArray(d) ? d : d?.results || []))
      .finally(() => setLoading(false));
    fade(() => setStep(3));
  }

  function pickYear(y) {
    setSel((s) => ({ ...s, year: y }));
    if (modifications.length > 0) {
      fade(() => setStep(4));
    } else {
      onSubmit?.({
        generationId: sel.generationId,
        modificationId: null,
        year: y,
        makeId: sel.makeId,
        modelId: sel.modelId,
        makeName: sel.makeName,
        modelName: sel.modelName,
        displayLabel: [String(y), sel.makeName, sel.modelName]
          .filter(Boolean)
          .join(" "),
      });
    }
  }

  function pickMod(modId) {
    onSubmit?.({
      generationId: sel.generationId,
      modificationId: modId || null,
      year: sel.year,
      makeId: sel.makeId,
      modelId: sel.modelId,
      makeName: sel.makeName,
      modelName: sel.modelName,
      displayLabel: [String(sel.year), sel.makeName, sel.modelName]
        .filter(Boolean)
        .join(" "),
    });
  }

  const years = [];
  for (let y = sel.yearMax; y >= sel.yearMin; y--) years.push(y);

  const q = search.trim().toLowerCase();
  const filteredMakes = q
    ? makes.filter((m) => m.name.toLowerCase().includes(q))
    : makes;
  const filteredModels = q
    ? models.filter((m) => m.name.toLowerCase().includes(q))
    : models;
  const filteredGenerations = q
    ? generations.filter((g) =>
        (g.display_label || g.name || "").toLowerCase().includes(q),
      )
    : generations;
  const showSearch =
    (step === 0 && makes.length > 6) ||
    (step === 1 && models.length > 6) ||
    (step === 2 && generations.length > 6);

  const crumbs = [
    sel.makeName,
    sel.modelName,
    sel.genLabel,
    sel.year ? String(sel.year) : null,
  ].filter(Boolean);
  const TITLES = [
    "Select make",
    "Select model",
    "Select generation",
    "Select year",
    "Select trim",
  ];

  const rowStyle = {
    width: "100%",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "12px 14px",
    borderRadius: 10,
    border: "1px solid var(--border)",
    background: "var(--bg-surface)",
    color: "var(--text-primary)",
    fontSize: 14,
    fontWeight: 500,
    fontFamily: "var(--ff-body)",
    cursor: "pointer",
    textAlign: "left",
  };

  const ChevRight = () => (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{
        width: 14,
        height: 14,
        color: "var(--text-muted)",
        flexShrink: 0,
      }}
      aria-hidden
    >
      <path d="M9 18l6-6-6-6" />
    </svg>
  );

  return (
    <div
      style={{
        background: "var(--bg-elevated)",
        border: "1px solid var(--border)",
        borderRadius: 16,
        overflow: "hidden",
        boxShadow: "0 8px 28px -4px rgba(0,0,0,0.1)",
      }}
    >
      {/* Header */}
      <div
        style={{
          background: "var(--bg-surface)",
          borderBottom: "1px solid var(--border)",
          padding: "10px 14px",
          display: "flex",
          alignItems: "center",
          gap: 8,
          minHeight: 46,
        }}
      >
        {step > 0 && (
          <button
            onClick={goBack}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "var(--text-muted)",
              padding: "4px 8px 4px 2px",
              display: "flex",
              alignItems: "center",
              flexShrink: 0,
            }}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              style={{ width: 15, height: 15 }}
              aria-hidden
            >
              <path d="M19 12H5M12 5l-7 7 7 7" />
            </svg>
          </button>
        )}
        <div
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            gap: 5,
            flexWrap: "wrap",
            overflow: "hidden",
          }}
        >
          {crumbs.length === 0 ? (
            <span
              style={{
                fontSize: 12,
                color: "var(--text-disabled)",
                fontFamily: "var(--ff-body)",
              }}
            >
              No car selected yet
            </span>
          ) : (
            crumbs.map((c, i) => (
              <React.Fragment key={i}>
                {i > 0 && (
                  <span style={{ fontSize: 10, color: "var(--text-disabled)" }}>
                    ›
                  </span>
                )}
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    fontFamily: "var(--ff-body)",
                    whiteSpace: "nowrap",
                    color:
                      i === crumbs.length - 1
                        ? "var(--text-primary)"
                        : "var(--text-muted)",
                  }}
                >
                  {c}
                </span>
              </React.Fragment>
            ))
          )}
        </div>
        <span
          style={{
            fontSize: 10,
            color: "var(--text-disabled)",
            fontFamily: "var(--ff-body)",
            whiteSpace: "nowrap",
            flexShrink: 0,
          }}
        >
          {step + 1} / 4
        </span>
      </div>

      {/* Step title */}
      <div style={{ padding: "12px 16px 8px" }}>
        <div
          style={{
            fontSize: 11,
            fontWeight: 700,
            color: "var(--text-muted)",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            fontFamily: "var(--ff-body)",
          }}
        >
          {TITLES[step]}
        </div>
      </div>

      {/* Search input */}
      {showSearch && !loading && (
        <div style={{ padding: "0 16px 8px" }}>
          <div style={{ position: "relative" }}>
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.75}
              strokeLinecap="round"
              strokeLinejoin="round"
              style={{
                position: "absolute",
                left: 10,
                top: "50%",
                transform: "translateY(-50%)",
                width: 13,
                height: 13,
                color: "var(--text-muted)",
                pointerEvents: "none",
              }}
              aria-hidden
            >
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.35-4.35" />
            </svg>
            <input
              type="text"
              placeholder="Search…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                width: "100%",
                background: "var(--bg-surface)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                padding: "8px 10px 8px 30px",
                fontSize: 13,
                color: "var(--text-primary)",
                fontFamily: "var(--ff-body)",
                outline: "none",
                boxSizing: "border-box",
              }}
            />
          </div>
        </div>
      )}

      {/* Options */}
      <div
        style={{
          padding: "0 16px 16px",
          maxHeight: 264,
          overflowY: "auto",
          opacity: fading ? 0 : 1,
          transition: "opacity 0.18s ease",
        }}
      >
        {loading && (
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              padding: "28px 0",
            }}
          >
            <div
              className="animate-spin"
              style={{
                width: 20,
                height: 20,
                borderRadius: "50%",
                border: "2px solid var(--border)",
                borderTopColor: "var(--primary)",
              }}
            />
          </div>
        )}

        {!loading && step === 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {filteredMakes.map((m) => (
              <button
                key={m.id}
                onClick={() => pickMake(m)}
                style={{
                  padding: "9px 16px",
                  borderRadius: 8,
                  border: "1px solid var(--border)",
                  background: "var(--bg-surface)",
                  color: "var(--text-primary)",
                  fontSize: 13,
                  fontFamily: "var(--ff-body)",
                  cursor: "pointer",
                  transition: "all 0.15s",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = "var(--primary)";
                  e.currentTarget.style.color = "var(--primary)";
                  e.currentTarget.style.background = "var(--primary-muted)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = "var(--border)";
                  e.currentTarget.style.color = "var(--text-primary)";
                  e.currentTarget.style.background = "var(--bg-surface)";
                }}
              >
                {m.name}
              </button>
            ))}
          </div>
        )}

        {!loading && step === 1 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
            {filteredModels.map((m) => (
              <button
                key={m.id}
                onClick={() => pickModel(m)}
                style={rowStyle}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor =
                    "var(--primary-border-strong)";
                  e.currentTarget.style.background = "var(--primary-muted)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = "var(--border)";
                  e.currentTarget.style.background = "var(--bg-surface)";
                }}
              >
                <span>{m.name}</span>
                <ChevRight />
              </button>
            ))}
          </div>
        )}

        {!loading && step === 2 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
            {filteredGenerations.map((g) => (
              <button
                key={g.id}
                onClick={() => pickGeneration(g)}
                style={rowStyle}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor =
                    "var(--primary-border-strong)";
                  e.currentTarget.style.background = "var(--primary-muted)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = "var(--border)";
                  e.currentTarget.style.background = "var(--bg-surface)";
                }}
              >
                <span>{g.display_label || g.name}</span>
                <ChevRight />
              </button>
            ))}
          </div>
        )}

        {!loading && step === 3 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {years.map((y) => (
              <button
                key={y}
                onClick={() => pickYear(y)}
                style={{
                  padding: "9px 15px",
                  borderRadius: 8,
                  border: "1px solid var(--border)",
                  background: "var(--bg-surface)",
                  color: "var(--text-primary)",
                  fontSize: 14,
                  fontWeight: 500,
                  fontFamily: "var(--ff-body)",
                  cursor: "pointer",
                  transition: "all 0.15s",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = "var(--primary)";
                  e.currentTarget.style.background = "var(--primary-muted)";
                  e.currentTarget.style.color = "var(--primary)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = "var(--border)";
                  e.currentTarget.style.background = "var(--bg-surface)";
                  e.currentTarget.style.color = "var(--text-primary)";
                }}
              >
                {y}
              </button>
            ))}
          </div>
        )}

        {!loading && step === 4 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
            <button
              onClick={() => pickMod(null)}
              style={{
                ...rowStyle,
                background: "var(--primary-muted)",
                border: "1px solid var(--primary-border-soft)",
                color: "var(--primary)",
                fontWeight: 600,
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = "var(--primary)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor =
                  "var(--primary-border-soft)";
              }}
            >
              <span>Any trim — show all parts</span>
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth={1.75}
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{ width: 14, height: 14, flexShrink: 0 }}
                aria-hidden
              >
                <path d="M5 12h14" />
                <path d="M12 5l7 7-7 7" />
              </svg>
            </button>
            {modifications.map((m) => (
              <button
                key={m.id}
                onClick={() => pickMod(m.id)}
                style={rowStyle}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor =
                    "var(--primary-border-strong)";
                  e.currentTarget.style.background = "var(--primary-muted)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = "var(--border)";
                  e.currentTarget.style.background = "var(--bg-surface)";
                }}
              >
                <span>{m.display_label || m.code}</span>
                <ChevRight />
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function BuyerSearch() {
  const router = useRouter();
  const { setCar } = useBuyerCar();

  async function handleSubmit(payload) {
    await setCar(payload);
    const params = new URLSearchParams({
      generation: String(payload.generationId),
      year: String(payload.year),
      compatible_only: "1",
    });
    if (payload.modificationId)
      params.set("modification", String(payload.modificationId));
    router.push(`/search?${params.toString()}`);
  }

  return (
    <section className="py-20 md:py-24">
      <div className="mx-auto max-w-2xl px-4 sm:px-6 lg:px-8">
        <Reveal className="text-center mb-10">
          <span className="section-label justify-center mb-4">For Buyers</span>
          <h2
            style={{
              fontFamily: "var(--ff-body)",
              fontWeight: 700,
              fontSize: "clamp(26px,4vw,46px)",
              letterSpacing: "-0.03em",
              color: "var(--text-primary)",
              lineHeight: 1.1,
              marginBottom: 12,
            }}
          >
            Find parts for your car.
          </h2>
          <p
            style={{
              fontSize: 15,
              color: "var(--text-secondary)",
              fontFamily: "var(--ff-body)",
            }}
          >
            Select your vehicle. See only parts verified to fit.
          </p>
        </Reveal>
        <Reveal delay={100}>
          <BuyerCarWizard onSubmit={handleSubmit} />
        </Reveal>
      </div>
    </section>
  );
}

/* ─── Speed comparison ──────────────────────────────────────────────────────── */

function SpeedComparison() {
  const lmpPoints = [
    "Post your car once",
    "All parts listed automatically",
    "OEM part data pre-filled",
    "Market pricing auto-suggested",
  ];
  const otherPoints = [
    "List each part one by one",
    "Write every description manually",
    "Research prices yourself",
    "Upload photos for each part",
  ];

  return (
    <section className="py-20 md:py-24 relative">
      <div
        className="absolute inset-0"
        style={{ background: "var(--bg-surface)" }}
      />
      <div
        className="absolute top-0 left-0 right-0 h-px"
        style={{
          background:
            "linear-gradient(to right, transparent, var(--border), transparent)",
        }}
      />
      <div
        className="absolute bottom-0 left-0 right-0 h-px"
        style={{
          background:
            "linear-gradient(to right, transparent, var(--border), transparent)",
        }}
      />

      <div className="relative mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
        <Reveal className="text-center mb-12">
          <span className="section-label justify-center mb-4">For Sellers</span>
          <h2
            style={{
              fontFamily: "var(--ff-body)",
              fontWeight: 700,
              fontSize: "clamp(26px,4.5vw,52px)",
              letterSpacing: "-0.03em",
              color: "var(--text-primary)",
              lineHeight: 1.08,
            }}
          >
            List your entire car.{" "}
            <span style={{ color: "var(--primary)" }}>In 1 minute.</span>
          </h2>
          <p
            style={{
              fontSize: 15,
              color: "var(--text-secondary)",
              fontFamily: "var(--ff-body)",
              marginTop: 12,
            }}
          >
            Not 3 to 7 days.
          </p>
        </Reveal>

        <div className="grid gap-5 sm:grid-cols-2 max-w-2xl mx-auto">
          {/* LookMyPart */}
          <Reveal>
            <div
              style={{
                background: "var(--primary-muted)",
                border: "2px solid var(--primary)",
                borderRadius: 20,
                padding: "28px 24px",
              }}
            >
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  color: "var(--primary)",
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  fontFamily: "var(--ff-body)",
                  marginBottom: 8,
                }}
              >
                LookMyPart
              </div>
              <div
                style={{
                  fontSize: 72,
                  fontWeight: 800,
                  color: "var(--primary)",
                  fontFamily: "var(--ff-body)",
                  letterSpacing: "-0.04em",
                  lineHeight: 1,
                }}
              >
                1
              </div>
              <div
                style={{
                  fontSize: 18,
                  fontWeight: 600,
                  color: "var(--primary)",
                  fontFamily: "var(--ff-body)",
                  marginBottom: 20,
                }}
              >
                minute
              </div>
              <div
                style={{
                  height: 1,
                  background: "var(--primary-border-soft)",
                  marginBottom: 20,
                }}
              />
              <div
                style={{ display: "flex", flexDirection: "column", gap: 10 }}
              >
                {lmpPoints.map((t) => (
                  <div
                    key={t}
                    style={{ display: "flex", alignItems: "center", gap: 10 }}
                  >
                    <div
                      style={{
                        width: 18,
                        height: 18,
                        borderRadius: "50%",
                        background: "var(--primary)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        flexShrink: 0,
                      }}
                    >
                      <svg
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="#fff"
                        strokeWidth={2.5}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        style={{ width: 10, height: 10 }}
                        aria-hidden
                      >
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    </div>
                    <span
                      style={{
                        fontSize: 13,
                        color: "var(--text-primary)",
                        fontFamily: "var(--ff-body)",
                      }}
                    >
                      {t}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </Reveal>

          {/* Other platforms */}
          <Reveal delay={80}>
            <div
              style={{
                background: "var(--bg-elevated)",
                border: "1px solid var(--border)",
                borderRadius: 20,
                padding: "28px 24px",
                opacity: 0.65,
              }}
            >
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  color: "var(--text-disabled)",
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  fontFamily: "var(--ff-body)",
                  marginBottom: 8,
                }}
              >
                Other platforms
              </div>
              <div
                style={{
                  fontSize: 72,
                  fontWeight: 800,
                  color: "var(--text-muted)",
                  fontFamily: "var(--ff-body)",
                  letterSpacing: "-0.04em",
                  lineHeight: 1,
                }}
              >
                3–7
              </div>
              <div
                style={{
                  fontSize: 18,
                  fontWeight: 600,
                  color: "var(--text-muted)",
                  fontFamily: "var(--ff-body)",
                  marginBottom: 20,
                }}
              >
                days
              </div>
              <div
                style={{
                  height: 1,
                  background: "var(--border)",
                  marginBottom: 20,
                }}
              />
              <div
                style={{ display: "flex", flexDirection: "column", gap: 10 }}
              >
                {otherPoints.map((t) => (
                  <div
                    key={t}
                    style={{ display: "flex", alignItems: "center", gap: 10 }}
                  >
                    <div
                      style={{
                        width: 18,
                        height: 18,
                        borderRadius: "50%",
                        background: "var(--bg-surface)",
                        border: "1px solid var(--border)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        flexShrink: 0,
                      }}
                    >
                      <svg
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="#ef4444"
                        strokeWidth={2.5}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        style={{ width: 9, height: 9 }}
                        aria-hidden
                      >
                        <path d="M18 6 6 18M6 6l12 12" />
                      </svg>
                    </div>
                    <span
                      style={{
                        fontSize: 13,
                        color: "var(--text-muted)",
                        fontFamily: "var(--ff-body)",
                      }}
                    >
                      {t}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

/* ─── Fitment callout ───────────────────────────────────────────────────────── */

function FitmentCallout() {
  return (
    <section className="py-20 md:py-24">
      <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
        <div className="grid gap-12 lg:grid-cols-2 items-center">
          <Reveal>
            <span className="section-label mb-4">For Buyers</span>
            <h2
              style={{
                fontFamily: "var(--ff-body)",
                fontWeight: 700,
                fontSize: "clamp(26px,4vw,46px)",
                letterSpacing: "-0.03em",
                color: "var(--text-primary)",
                lineHeight: 1.1,
                marginBottom: 16,
              }}
            >
              Only parts that fit
              <br />
              <span style={{ color: "var(--primary)" }}>your exact car.</span>
            </h2>
            <p
              style={{
                fontSize: 15,
                color: "var(--text-secondary)",
                lineHeight: 1.7,
                fontFamily: "var(--ff-body)",
                maxWidth: 380,
              }}
            >
              Select your year, make, and model. Every result is verified to fit
              your exact vehicle. No guessing if it&apos;s compatible.
            </p>
          </Reveal>

          <Reveal direction="left" delay={100}>
            <div
              style={{
                background: "var(--bg-surface)",
                border: "1px solid var(--border)",
                borderRadius: 16,
                overflow: "hidden",
                boxShadow: "0 16px 40px -8px rgba(0,0,0,0.12)",
              }}
            >
              <div
                style={{
                  background: "rgba(34,197,94,0.09)",
                  borderBottom: "1px solid rgba(34,197,94,0.2)",
                  padding: "10px 16px",
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2.2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{
                    width: 14,
                    height: 14,
                    color: "var(--success)",
                    flexShrink: 0,
                  }}
                  aria-hidden
                >
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: "var(--success)",
                    fontFamily: "var(--ff-body)",
                  }}
                >
                  Fits your 2018 Ford F-150 XLT · 5.0L V8
                </span>
              </div>
              <div style={{ display: "flex", gap: 14, padding: "16px" }}>
                <div
                  style={{
                    width: 68,
                    height: 68,
                    borderRadius: 10,
                    background: "var(--bg-elevated)",
                    border: "1px solid var(--border)",
                    flexShrink: 0,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={1.5}
                    style={{
                      width: 22,
                      height: 22,
                      color: "var(--text-disabled)",
                    }}
                    aria-hidden
                  >
                    <rect x="3" y="3" width="18" height="18" rx="2" />
                    <circle cx="8.5" cy="8.5" r="1.5" />
                    <path d="M21 15l-5-5L5 21" />
                  </svg>
                </div>
                <div style={{ flex: 1 }}>
                  <div
                    style={{
                      fontSize: 15,
                      fontWeight: 700,
                      color: "var(--text-primary)",
                      fontFamily: "var(--ff-body)",
                      marginBottom: 3,
                    }}
                  >
                    Alternator
                  </div>
                  <div
                    style={{
                      fontSize: 11,
                      color: "var(--text-disabled)",
                      fontFamily: "var(--ff-mono)",
                      marginBottom: 10,
                    }}
                  >
                    Part# DL3Z-10346-A · Condition: Good
                  </div>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <span
                      style={{
                        fontSize: 20,
                        fontWeight: 800,
                        color: "var(--primary)",
                        fontFamily: "var(--ff-body)",
                        letterSpacing: "-0.02em",
                      }}
                    >
                      $95
                    </span>
                    <div
                      style={{
                        background: "var(--primary)",
                        borderRadius: 8,
                        padding: "7px 16px",
                        fontSize: 13,
                        fontWeight: 600,
                        color: "#fff",
                        fontFamily: "var(--ff-body)",
                      }}
                    >
                      Buy Now
                    </div>
                  </div>
                </div>
              </div>
              <div
                style={{
                  borderTop: "1px solid var(--border)",
                  padding: "10px 16px",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <span
                  style={{
                    fontSize: 11,
                    color: "var(--text-muted)",
                    fontFamily: "var(--ff-body)",
                  }}
                >
                  Shipping shown before checkout
                </span>
                <span
                  style={{
                    fontSize: 11,
                    color: "var(--text-muted)",
                    fontFamily: "var(--ff-body)",
                  }}
                >
                  30-day return
                </span>
              </div>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

/* ─── Shipping tiers ────────────────────────────────────────────────────────── */

function ShippingTiers() {
  const marketRoutes = [
    { from: "TX → CA", ours: "$100–$150", market: "~$400–600" },
    { from: "TX → NY", ours: "$100–$150", market: "~$500–800" },
    { from: "TX → FL", ours: "$100–$150", market: "~$350–550" },
  ];

  return (
    <section id="shipping" className="py-20 md:py-24 relative">
      <div
        className="absolute inset-0"
        style={{ background: "var(--bg-surface)" }}
      />
      <div
        className="absolute top-0 left-0 right-0 h-px"
        style={{
          background:
            "linear-gradient(to right, transparent, var(--border), transparent)",
        }}
      />
      <div
        className="absolute bottom-0 left-0 right-0 h-px"
        style={{
          background:
            "linear-gradient(to right, transparent, var(--border), transparent)",
        }}
      />

      <div className="relative mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
        <Reveal className="text-center mb-12">
          <span className="section-label justify-center mb-4">Shipping</span>
          <h2
            style={{
              fontFamily: "var(--ff-body)",
              fontWeight: 700,
              fontSize: "clamp(26px,4vw,46px)",
              letterSpacing: "-0.03em",
              color: "var(--text-primary)",
              lineHeight: 1.1,
            }}
          >
            Know the cost before you commit.
          </h2>
          <p
            style={{
              fontSize: 15,
              color: "var(--text-secondary)",
              fontFamily: "var(--ff-body)",
              marginTop: 12,
              maxWidth: 480,
              margin: "12px auto 0",
            }}
          >
            Shipping cost is always shown before checkout — no surprises.
          </p>
        </Reveal>

        {/* ── Economy freight hero ── */}
        <Reveal>
          <div
            style={{
              position: "relative",
              background: "var(--primary-muted)",
              border: "2px solid var(--primary)",
              borderRadius: 20,
              padding: "32px 28px",
              marginBottom: 16,
              overflow: "hidden",
            }}
          >
            {/* Exclusive badge */}
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                background: "var(--primary)",
                color: "#fff",
                borderRadius: 20,
                padding: "4px 12px",
                fontSize: 11,
                fontWeight: 700,
                fontFamily: "var(--ff-body)",
                letterSpacing: "0.04em",
                textTransform: "uppercase",
                marginBottom: 20,
              }}
            >
              <svg
                viewBox="0 0 24 24"
                fill="currentColor"
                style={{ width: 10, height: 10 }}
                aria-hidden
              >
                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
              </svg>
              Only on LookMyPart
            </div>

            <div className="grid gap-8 sm:grid-cols-2 items-center">
              {/* Left: the offer */}
              <div>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    color: "var(--primary)",
                    fontFamily: "var(--ff-body)",
                    textTransform: "uppercase",
                    letterSpacing: "0.08em",
                    marginBottom: 6,
                  }}
                >
                  Large Parts · Economy Freight
                </div>
                <div
                  style={{
                    display: "flex",
                    alignItems: "baseline",
                    gap: 4,
                    marginBottom: 4,
                  }}
                >
                  <span
                    style={{
                      fontSize: "clamp(52px,7vw,72px)",
                      fontWeight: 800,
                      color: "var(--primary)",
                      fontFamily: "var(--ff-body)",
                      letterSpacing: "-0.04em",
                      lineHeight: 1,
                    }}
                  >
                    $100
                  </span>
                  <span
                    style={{
                      fontSize: 28,
                      fontWeight: 700,
                      color: "var(--primary)",
                      fontFamily: "var(--ff-body)",
                      opacity: 0.7,
                    }}
                  >
                    – $150
                  </span>
                </div>
                <div
                  style={{
                    fontSize: 16,
                    fontWeight: 600,
                    color: "var(--text-primary)",
                    fontFamily: "var(--ff-body)",
                    marginBottom: 10,
                  }}
                >
                  Flat rate. Anywhere in the US.
                </div>
                <p
                  style={{
                    fontSize: 13,
                    color: "var(--text-secondary)",
                    fontFamily: "var(--ff-body)",
                    lineHeight: 1.6,
                    maxWidth: 320,
                  }}
                >
                  Engines, transmissions, body panels, doors — any large part
                  shipped coast-to-coast for one fixed price. No other
                  marketplace does this.
                </p>
                <div
                  style={{
                    marginTop: 14,
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={1.75}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    style={{
                      width: 13,
                      height: 13,
                      color: "var(--text-muted)",
                      flexShrink: 0,
                    }}
                    aria-hidden
                  >
                    <circle cx="12" cy="12" r="10" />
                    <path d="M12 6v6l4 2" />
                  </svg>
                  <span
                    style={{
                      fontSize: 12,
                      color: "var(--text-muted)",
                      fontFamily: "var(--ff-body)",
                    }}
                  >
                    30 – 45 days · Economy Freight carrier
                  </span>
                </div>
              </div>

              {/* Right: comparison table */}
              <div
                style={{
                  background: "var(--bg-elevated)",
                  border: "1px solid var(--border)",
                  borderRadius: 14,
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    padding: "12px 16px",
                    borderBottom: "1px solid var(--border)",
                    display: "flex",
                    justifyContent: "space-between",
                  }}
                >
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      textTransform: "uppercase",
                      letterSpacing: "0.08em",
                      color: "var(--text-disabled)",
                      fontFamily: "var(--ff-body)",
                    }}
                  >
                    Route
                  </span>
                  <div style={{ display: "flex", gap: 24 }}>
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 700,
                        textTransform: "uppercase",
                        letterSpacing: "0.08em",
                        color: "var(--primary)",
                        fontFamily: "var(--ff-body)",
                      }}
                    >
                      Us
                    </span>
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 700,
                        textTransform: "uppercase",
                        letterSpacing: "0.08em",
                        color: "var(--text-disabled)",
                        fontFamily: "var(--ff-body)",
                      }}
                    >
                      Market
                    </span>
                  </div>
                </div>
                {marketRoutes.map((r, i) => (
                  <div
                    key={r.from}
                    style={{
                      padding: "11px 16px",
                      borderBottom:
                        i < marketRoutes.length - 1
                          ? "1px solid var(--border)"
                          : "none",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <span
                      style={{
                        fontSize: 12,
                        color: "var(--text-secondary)",
                        fontFamily: "var(--ff-mono)",
                      }}
                    >
                      {r.from}
                    </span>
                    <div
                      style={{ display: "flex", gap: 24, alignItems: "center" }}
                    >
                      <span
                        style={{
                          fontSize: 13,
                          fontWeight: 700,
                          color: "var(--primary)",
                          fontFamily: "var(--ff-mono)",
                          minWidth: 72,
                          textAlign: "right",
                        }}
                      >
                        {r.ours}
                      </span>
                      <span
                        style={{
                          fontSize: 12,
                          color: "var(--text-disabled)",
                          fontFamily: "var(--ff-mono)",
                          textDecoration: "line-through",
                          minWidth: 72,
                          textAlign: "right",
                        }}
                      >
                        {r.market}
                      </span>
                    </div>
                  </div>
                ))}
                <div
                  style={{
                    padding: "10px 16px",
                    background: "rgba(34,197,94,0.06)",
                    borderTop: "1px solid rgba(34,197,94,0.15)",
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2.2}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    style={{
                      width: 12,
                      height: 12,
                      color: "var(--success)",
                      flexShrink: 0,
                    }}
                    aria-hidden
                  >
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: "var(--success)",
                      fontFamily: "var(--ff-body)",
                    }}
                  >
                    You save $300–700 per large shipment
                  </span>
                </div>
              </div>
            </div>
          </div>
        </Reveal>

        {/* ── Other tiers ── */}
        <div className="grid gap-4 sm:grid-cols-2">
          {/* Small & Medium */}
          <Reveal delay={60}>
            <div
              style={{
                background: "var(--bg-elevated)",
                border: "1px solid var(--border)",
                borderRadius: 16,
                padding: "22px 20px",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  marginBottom: 14,
                }}
              >
                <div
                  style={{
                    width: 34,
                    height: 34,
                    borderRadius: 10,
                    background: "var(--primary-muted)",
                    border: "1px solid var(--primary-border-soft)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "var(--primary)",
                    flexShrink: 0,
                  }}
                >
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={1.75}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    style={{ width: 15, height: 15 }}
                    aria-hidden
                  >
                    <rect x="1" y="3" width="15" height="13" rx="1" />
                    <path d="M16 8h4l3 5v4h-7V8z" />
                    <circle cx="5.5" cy="18.5" r="2.5" />
                    <circle cx="18.5" cy="18.5" r="2.5" />
                  </svg>
                </div>
                <div>
                  <div
                    style={{
                      fontSize: 13,
                      fontWeight: 700,
                      color: "var(--text-primary)",
                      fontFamily: "var(--ff-body)",
                    }}
                  >
                    Small &amp; Medium Parts
                  </div>
                  <div
                    style={{
                      fontSize: 11,
                      color: "var(--text-muted)",
                      fontFamily: "var(--ff-body)",
                    }}
                  >
                    USPS &amp; FedEx
                  </div>
                </div>
              </div>
              <div
                style={{
                  fontSize: 22,
                  fontWeight: 800,
                  color: "var(--primary)",
                  fontFamily: "var(--ff-mono)",
                  letterSpacing: "-0.02em",
                  marginBottom: 4,
                }}
              >
                Carrier rate
              </div>
              <div
                style={{
                  fontSize: 11,
                  color: "var(--text-muted)",
                  fontFamily: "var(--ff-body)",
                  marginBottom: 12,
                }}
              >
                Shown at checkout
              </div>
              <p
                style={{
                  fontSize: 12,
                  color: "var(--text-muted)",
                  fontFamily: "var(--ff-body)",
                  lineHeight: 1.55,
                }}
              >
                Exact carrier cost calculated before you pay. No surprises.
              </p>
            </div>
          </Reveal>

          {/* Large Fast */}
          <Reveal delay={120}>
            <div
              style={{
                background: "var(--bg-elevated)",
                border: "1px solid var(--border)",
                borderRadius: 16,
                padding: "22px 20px",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  marginBottom: 14,
                }}
              >
                <div
                  style={{
                    width: 34,
                    height: 34,
                    borderRadius: 10,
                    background: "var(--primary-muted)",
                    border: "1px solid var(--primary-border-soft)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "var(--primary)",
                    flexShrink: 0,
                  }}
                >
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={1.75}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    style={{ width: 15, height: 15 }}
                    aria-hidden
                  >
                    <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
                  </svg>
                </div>
                <div>
                  <div
                    style={{
                      fontSize: 13,
                      fontWeight: 700,
                      color: "var(--text-primary)",
                      fontFamily: "var(--ff-body)",
                    }}
                  >
                    Large Parts · Fast Freight
                  </div>
                  <div
                    style={{
                      fontSize: 11,
                      color: "var(--text-muted)",
                      fontFamily: "var(--ff-body)",
                    }}
                  >
                    2 – 7 days · By route
                  </div>
                </div>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                {[
                  { from: "TX → CA", price: "$650" },
                  { from: "TX → NY", price: "$900" },
                  { from: "TX → FL", price: "$750" },
                ].map((r) => (
                  <div
                    key={r.from}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <span
                      style={{
                        fontSize: 12,
                        color: "var(--text-secondary)",
                        fontFamily: "var(--ff-mono)",
                      }}
                    >
                      {r.from}
                    </span>
                    <span
                      style={{
                        fontSize: 13,
                        fontWeight: 700,
                        color: "var(--primary)",
                        fontFamily: "var(--ff-mono)",
                      }}
                    >
                      {r.price}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

/* ─── Page ───────────────────────────────────────────────────────────────────── */

export default function Home() {
  const { user, loading: authLoading } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)" }}>
      {/* ── Navbar ─────────────────────────────────────────────────────────── */}
      <nav
        className="fixed left-0 right-0 top-0 z-[300]"
        style={{
          background: "var(--nav-bg)",
          backdropFilter: "blur(16px)",
          borderBottom: "1px solid var(--border-subtle)",
        }}
      >
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <Link href="/" className="flex items-center gap-2.5">
            <div
              className="flex h-8 w-8 items-center justify-center rounded-[8px]"
              style={{ background: "var(--primary)" }}
            >
              <span
                style={{
                  fontFamily: "var(--ff-body)",
                  fontWeight: 800,
                  fontSize: 15,
                  color: "#fff",
                }}
              >
                L
              </span>
            </div>
            <span
              style={{
                fontFamily: "var(--ff-body)",
                fontWeight: 700,
                fontSize: 16,
                letterSpacing: "-0.01em",
                color: "var(--text-primary)",
              }}
            >
              LookMyPart
            </span>
          </Link>
          <div className="hidden items-center gap-2 md:flex">
            <ThemeToggle />
            {!authLoading && !user && (
              <>
                <Link
                  href="/login"
                  className="px-4 py-2 text-sm font-medium"
                  style={{
                    color: "var(--text-muted)",
                    fontFamily: "var(--ff-body)",
                  }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.color = "var(--text-primary)")
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.color = "var(--text-muted)")
                  }
                >
                  Log in
                </Link>
                <Link
                  href="/register"
                  className="btn-forge"
                  style={{ padding: "8px 20px", fontSize: 13 }}
                >
                  Sign up free
                </Link>
              </>
            )}
            {user && (
              <>
                <Link
                  href="/cart"
                  className="px-3.5 py-2 text-sm font-medium"
                  style={{ color: "var(--text-muted)" }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.color = "var(--text-primary)")
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.color = "var(--text-muted)")
                  }
                >
                  Cart
                </Link>
                <Link
                  href="/dashboard"
                  className="btn-forge"
                  style={{ padding: "8px 20px", fontSize: 13 }}
                >
                  Dashboard
                </Link>
              </>
            )}
          </div>
          <div className="flex items-center gap-1.5 md:hidden">
            <ThemeToggle />
            <button
              onClick={() => setMobileOpen((o) => !o)}
              className="rounded-[8px] p-2"
              style={{ color: "var(--text-muted)" }}
              aria-label="Toggle menu"
            >
              {mobileOpen ? <IcX c="h-5 w-5" /> : <IcMenu c="h-5 w-5" />}
            </button>
          </div>
        </div>
        <AnimatePresence>
          {mobileOpen && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2 }}
              className="md:hidden p-4"
              style={{
                background: "var(--bg-base)",
                borderTop: "1px solid var(--border-subtle)",
              }}
            >
              <div className="flex flex-col gap-2">
                {!authLoading && !user && (
                  <>
                    <Link
                      href="/login"
                      className="px-3 py-2 text-sm"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      Log in
                    </Link>
                    <Link href="/register" className="btn-forge justify-center">
                      Sign up free
                    </Link>
                  </>
                )}
                {user && (
                  <Link href="/dashboard" className="btn-forge justify-center">
                    Dashboard
                  </Link>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </nav>

      {/* ── Hero ───────────────────────────────────────────────────────────── */}
      <section
        className="pt-32 pb-8 md:pt-40 md:pb-10"
        style={{ textAlign: "center" }}
      >
        <motion.div
          className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        >
          <motion.h1
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              duration: 0.7,
              delay: 0.05,
              ease: [0.22, 1, 0.36, 1],
            }}
            style={{
              fontFamily: "var(--ff-body)",
              fontWeight: 700,
              fontSize: "clamp(38px,6.5vw,72px)",
              letterSpacing: "-0.03em",
              color: "var(--text-primary)",
              lineHeight: 1.05,
              marginBottom: 20,
            }}
          >
            Car parts.{" "}
            <span style={{ color: "var(--primary)" }}>
              Bought and sold simply.
            </span>
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              duration: 0.6,
              delay: 0.14,
              ease: [0.22, 1, 0.36, 1],
            }}
            style={{
              fontSize: "clamp(16px,2.2vw,20px)",
              color: "var(--text-secondary)",
              fontFamily: "var(--ff-body)",
              maxWidth: 440,
              margin: "0 auto 28px",
              lineHeight: 1.6,
            }}
          >
            Sell your car&apos;s parts in minutes. Find the exact part your car
            needs.
          </motion.p>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.55, duration: 0.5 }}
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 6,
            }}
          >
            <span
              style={{
                fontSize: 10,
                color: "var(--text-disabled)",
                textTransform: "uppercase",
                letterSpacing: "0.12em",
                fontFamily: "var(--ff-body)",
              }}
            >
              Scroll to see how it works
            </span>
            <motion.div
              animate={{ y: [0, 5, 0] }}
              transition={{
                duration: 1.4,
                repeat: Infinity,
                ease: "easeInOut",
              }}
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth={1.75}
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{ width: 15, height: 15, color: "var(--text-disabled)" }}
                aria-hidden
              >
                <path d="m6 9 6 6 6-6" />
              </svg>
            </motion.div>
          </motion.div>
        </motion.div>
      </section>

      {/* ── Scroll demo ────────────────────────────────────────────────────── */}
      <ScrollDemo />

      {/* ── List your entire car ───────────────────────────────────────────── */}
      <SpeedComparison />

      {/* ── Only parts that fit ────────────────────────────────────────────── */}
      <FitmentCallout />

      {/* ── Shipping ───────────────────────────────────────────────────────── */}
      <ShippingTiers />

      {/* ── CTA split ──────────────────────────────────────────────────────── */}
      <div
        className="grid sm:grid-cols-2"
        style={{ borderTop: "1px solid var(--border-subtle)" }}
      >
        <div
          style={{
            background: "var(--primary)",
            padding: "52px 32px",
            textAlign: "center",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
          }}
        >
          <div
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: "rgba(255,255,255,0.6)",
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              fontFamily: "var(--ff-body)",
              marginBottom: 12,
            }}
          >
            For Sellers
          </div>
          <h3
            style={{
              fontFamily: "var(--ff-body)",
              fontWeight: 700,
              fontSize: "clamp(20px,3vw,30px)",
              color: "#fff",
              lineHeight: 1.15,
              marginBottom: 12,
            }}
          >
            Have a car to part out?
          </h3>
          <p
            style={{
              fontSize: 14,
              color: "rgba(255,255,255,0.72)",
              fontFamily: "var(--ff-body)",
              lineHeight: 1.6,
              maxWidth: 280,
              marginBottom: 24,
            }}
          >
            List it in minutes. 240 parts posted automatically with exact OEM
            data and real market pricing.
          </p>
          <Link
            href={user ? "/vehicles/new" : "/register"}
            style={{
              background: "#fff",
              color: "var(--primary)",
              borderRadius: 10,
              padding: "13px 32px",
              fontSize: 14,
              fontWeight: 700,
              fontFamily: "var(--ff-body)",
              textDecoration: "none",
            }}
          >
            List your vehicle
          </Link>
        </div>
        <div
          style={{
            background: "var(--bg-elevated)",
            padding: "52px 32px",
            textAlign: "center",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
          }}
        >
          <div
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: "var(--text-disabled)",
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              fontFamily: "var(--ff-body)",
              marginBottom: 12,
            }}
          >
            For Buyers
          </div>
          <h3
            style={{
              fontFamily: "var(--ff-body)",
              fontWeight: 700,
              fontSize: "clamp(20px,3vw,30px)",
              color: "var(--text-primary)",
              lineHeight: 1.15,
              marginBottom: 12,
            }}
          >
            Looking for a part?
          </h3>
          <p
            style={{
              fontSize: 14,
              color: "var(--text-muted)",
              fontFamily: "var(--ff-body)",
              lineHeight: 1.6,
              maxWidth: 280,
              marginBottom: 24,
            }}
          >
            Search by your car. Every result is verified to fit. Shipping cost
            shown before you commit.
          </p>
          <Link
            href="/search"
            style={{
              background: "var(--primary)",
              color: "#fff",
              borderRadius: 10,
              padding: "13px 32px",
              fontSize: 14,
              fontWeight: 700,
              fontFamily: "var(--ff-body)",
              textDecoration: "none",
            }}
          >
            Search parts
          </Link>
        </div>
      </div>

      {/* ── Buyer search widget ────────────────────────────────────────────── */}
      <BuyerSearch />

      {/* <FeaturedCategories /> */}
      {/* <RecentParts /> */}
      {/* <MakeStrip /> */}

      {/* ── Footer ──────────────────────────────────────────────────────────── */}
      <footer
        style={{
          borderTop: "1px solid var(--border-subtle)",
          background: "var(--bg-surface)",
          padding: "52px 0 32px",
        }}
      >
        <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
          <div
            className="grid gap-10 sm:grid-cols-3"
            style={{ marginBottom: 40 }}
          >
            <div>
              <Link
                href="/"
                className="flex items-center gap-2.5"
                style={{ marginBottom: 12, textDecoration: "none" }}
              >
                <div
                  className="flex h-8 w-8 items-center justify-center rounded-[8px]"
                  style={{ background: "var(--primary)" }}
                >
                  <span
                    style={{
                      fontFamily: "var(--ff-body)",
                      fontWeight: 800,
                      fontSize: 15,
                      color: "#fff",
                    }}
                  >
                    L
                  </span>
                </div>
                <span
                  style={{
                    fontFamily: "var(--ff-body)",
                    fontWeight: 700,
                    fontSize: 16,
                    letterSpacing: "-0.01em",
                    color: "var(--text-primary)",
                  }}
                >
                  LookMyPart
                </span>
              </Link>
              <p
                style={{
                  fontSize: 13,
                  color: "var(--text-muted)",
                  fontFamily: "var(--ff-body)",
                  lineHeight: 1.6,
                }}
              >
                The used car parts marketplace. Transparent pricing, exact
                fitment data, clear shipping.
              </p>
            </div>
            <div>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  color: "var(--text-muted)",
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  fontFamily: "var(--ff-body)",
                  marginBottom: 14,
                }}
              >
                Sellers
              </div>
              <div
                style={{ display: "flex", flexDirection: "column", gap: 12 }}
              >
                {[
                  ["List your vehicle", "/register"],
                  ["My vehicles", "/vehicles"],
                  ["Sales & orders", "/orders"],
                  ["Earnings", "/money"],
                ].map(([label, href]) => (
                  <Link
                    key={href}
                    href={href}
                    style={{
                      fontSize: 13,
                      color: "var(--text-muted)",
                      fontFamily: "var(--ff-body)",
                      textDecoration: "none",
                    }}
                    onMouseEnter={(e) =>
                      (e.currentTarget.style.color = "var(--text-primary)")
                    }
                    onMouseLeave={(e) =>
                      (e.currentTarget.style.color = "var(--text-muted)")
                    }
                  >
                    {label}
                  </Link>
                ))}
              </div>
            </div>
            <div>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  color: "var(--text-muted)",
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  fontFamily: "var(--ff-body)",
                  marginBottom: 14,
                }}
              >
                Buyers
              </div>
              <div
                style={{ display: "flex", flexDirection: "column", gap: 12 }}
              >
                {[
                  ["Browse parts", "/search"],
                  ["My purchases", "/purchases"],
                  ["Cart", "/cart"],
                  ["Sign in", "/login"],
                ].map(([label, href]) => (
                  <Link
                    key={href}
                    href={href}
                    style={{
                      fontSize: 13,
                      color: "var(--text-muted)",
                      fontFamily: "var(--ff-body)",
                      textDecoration: "none",
                    }}
                    onMouseEnter={(e) =>
                      (e.currentTarget.style.color = "var(--text-primary)")
                    }
                    onMouseLeave={(e) =>
                      (e.currentTarget.style.color = "var(--text-muted)")
                    }
                  >
                    {label}
                  </Link>
                ))}
              </div>
            </div>
          </div>
          <div
            style={{
              borderTop: "1px solid var(--border-subtle)",
              paddingTop: 24,
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 8,
            }}
          >
            <p
              style={{
                fontSize: 12,
                color: "var(--text-disabled)",
                fontFamily: "var(--ff-body)",
              }}
            >
              © 2026 LookMyPart
            </p>
            <p
              style={{
                fontSize: 12,
                color: "var(--text-disabled)",
                fontFamily: "var(--ff-body)",
              }}
            >
              Used car parts marketplace
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
