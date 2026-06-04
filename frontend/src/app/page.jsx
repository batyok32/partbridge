"use client";

import React, { useEffect, useRef, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { motion, useScroll, useTransform, AnimatePresence } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { ThemeToggle } from "@/components/ThemeToggle";
import FeaturedCategories from "@/components/home/FeaturedCategories";
import HomeCarHero from "@/components/home/HomeCarHero";
import HowItWorksBuyer from "@/components/home/HowItWorksBuyer";
import MakeStrip from "@/components/home/MakeStrip";
import RecentParts from "@/components/home/RecentParts";

/* ─── Scroll-triggered fade-in ─────────────────────────────────────────────── */

function useInView(threshold = 0.1) {
  const ref = useRef(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setInView(true); obs.disconnect(); } }, { threshold });
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);
  return [ref, inView];
}

function Reveal({ children, delay = 0, className = "", direction = "up" }) {
  const [ref, inView] = useInView();
  const yStart = direction === "up" ? 24 : direction === "down" ? -24 : 0;
  const xStart = direction === "right" ? -24 : direction === "left" ? 24 : 0;
  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: inView ? 1 : 0,
        transform: inView ? "translate(0,0)" : `translate(${xStart}px,${yStart}px)`,
        transition: `opacity 0.65s cubic-bezier(0.22,1,0.36,1) ${delay}ms, transform 0.65s cubic-bezier(0.22,1,0.36,1) ${delay}ms`,
      }}
    >
      {children}
    </div>
  );
}

/* ─── Icons (inline SVG) ────────────────────────────────────────────────────── */

const S = ({ className, children }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>{children}</svg>
);

const IcSearch    = ({ c }) => <S className={c}><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></S>;
const IcCar       = ({ c }) => <S className={c}><path d="M19 17H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h3l2-3h4l2 3h3a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2z"/><circle cx="7" cy="17" r="2"/><circle cx="17" cy="17" r="2"/></S>;
const IcCamera    = ({ c }) => <S className={c}><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></S>;
const IcTrending  = ({ c }) => <S className={c}><path d="M22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></S>;
const IcDollar    = ({ c }) => <S className={c}><path d="M12 1v22M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></S>;
const IcShield    = ({ c }) => <S className={c}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></S>;
const IcCard      = ({ c }) => <S className={c}><rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/></S>;
const IcPackage   = ({ c }) => <S className={c}><path d="M16.5 9.4 7.55 4.24"/><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></S>;
const IcBarChart  = ({ c }) => <S className={c}><path d="M12 20V10"/><path d="M18 20V4"/><path d="M6 20v-4"/></S>;
const IcMessage   = ({ c }) => <S className={c}><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></S>;
const IcTruck     = ({ c }) => <S className={c}><rect x="1" y="3" width="15" height="13" rx="1"/><path d="M16 8h4l3 5v4h-7V8z"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/></S>;
const IcCog       = ({ c }) => <S className={c}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></S>;
const IcZap       = ({ c }) => <S className={c}><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/></S>;
const IcSnowflake = ({ c }) => <S className={c}><path d="M2 12h20M12 2v20M20 16l-4-4 4-4M4 8l4 4-4 4M16 4l-4 4-4-4M8 20l4-4 4 4"/></S>;
const IcFuel      = ({ c }) => <S className={c}><path d="M3 22V4a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v18"/><path d="M3 11h11"/><path d="M16 5s2 2 2 4-2 4-2 4"/></S>;
const IcWind      = ({ c }) => <S className={c}><path d="M17.7 7.7a2.5 2.5 0 1 1 1.8 4.3H2"/><path d="M9.6 4.6A2 2 0 1 1 11 8H2"/><path d="M12.6 19.4A2 2 0 1 0 14 16H2"/></S>;
const IcArrow     = ({ c }) => <S className={c}><path d="M5 12h14"/><path d="M13 6l6 6-6 6"/></S>;
const IcChevDown  = ({ c }) => <S className={c}><path d="m6 9 6 6 6-6"/></S>;
const IcMenu      = ({ c }) => <S className={c}><path d="M4 6h16M4 12h16M4 18h16"/></S>;
const IcX         = ({ c }) => <S className={c}><path d="M18 6 6 18m0-12 12 12"/></S>;
const IcCheck     = ({ c }) => <S className={c}><polyline points="20 6 9 17 4 12"/></S>;

/* ─── Static data ───────────────────────────────────────────────────────────── */

const YEARS = Array.from({ length: new Date().getFullYear() - 1979 }, (_, i) => String(new Date().getFullYear() - i));

const SELLER_STEPS = [
  { Icon: IcCar,      n: "01", title: "Enter Your VIN",         desc: "We decode it instantly — year, make, model, engine, trim. No manual entry needed." },
  { Icon: IcCamera,   n: "02", title: "Upload Photos",           desc: "Exterior, engine bay, interior, odometer. Your car is listed and all parts become visible." },
  { Icon: IcTrending, n: "03", title: "See What Parts Are Worth",desc: "Real eBay market data shows you low, average, and high prices for every part on your car." },
  { Icon: IcDollar,   n: "04", title: "Set Prices & Sell",       desc: "Price any part and it's instantly a Buy Now listing. Buyers come to you." },
];

const BUYER_STEPS = [
  { Icon: IcSearch,  n: "01", title: "Search Your Vehicle",  desc: "Select year, make, and the part you need. We show you every verified match." },
  { Icon: IcShield,  n: "02", title: "Verified Condition",   desc: "See real photos, condition grades, and the return policy before you commit." },
  { Icon: IcCard,    n: "03", title: "Buy Now or Message",   desc: "Purchase instantly at the listed price, or message the seller directly." },
  { Icon: IcPackage, n: "04", title: "Tracked Delivery",     desc: "Every order is tracked end-to-end. Shipping tiers and costs shown before checkout." },
];

const VALUE_PROPS = [
  { Icon: IcBarChart, title: "Real Market Pricing",     desc: "Every part shows prices from real sold eBay listings — no more guessing what your parts are worth." },
  { Icon: IcShield,   title: "Buyer Protection",        desc: "Refund rules are posted on every listing before you pay. Checkout keeps the details on record." },
  { Icon: IcMessage,  title: "Direct Communication",    desc: "Real-time messaging between buyer and seller. Ask questions, request more photos — before you commit." },
  { Icon: IcTruck,    title: "Transparent Shipping",    desc: "Shipping tiers and estimates shown upfront. No surprise charges waiting for you at checkout." },
];

const CATEGORIES = [
  { Icon: IcCog,       name: "Engine",      slug: "engine" },
  { Icon: IcCog,       name: "Brakes",      slug: "brakes" },
  { Icon: IcCog,       name: "Drivetrain",  slug: "drivetrain" },
  { Icon: IcZap,       name: "Electrical",  slug: "electrical" },
  { Icon: IcCar,       name: "Body Panels", slug: "body" },
  { Icon: IcSnowflake, name: "HVAC",        slug: "hvac" },
  { Icon: IcFuel,      name: "Fuel System", slug: "fuel" },
  { Icon: IcWind,      name: "Exhaust",     slug: "exhaust" },
];

const STATS = [
  { value: "2,400+", label: "Parts Listed" },
  { value: "850+",   label: "Donor Vehicles" },
  { value: "100%",   label: "Transparent Pricing" },
];

/* ─── SelectField ────────────────────────────────────────────────────────────── */

function SelectField({ value, onChange, placeholder, options, disabled = false }) {
  return (
    <div className="relative flex-1 min-w-[110px]">
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        disabled={disabled}
        className="h-11 w-full appearance-none rounded-[8px] px-4 pr-9 text-sm focus:outline-none disabled:opacity-40 disabled:cursor-not-allowed"
        style={{
          background: "var(--bg-elevated)",
          border: "1px solid var(--border)",
          color: value ? "var(--text-primary)" : "var(--text-muted)",
          fontFamily: "var(--ff-body)",
          transition: "border-color 0.15s, box-shadow 0.15s",
        }}
        onFocus={e => { e.target.style.borderColor = "var(--primary)"; e.target.style.boxShadow = "0 0 0 3px var(--primary-muted)"; }}
        onBlur={e => { e.target.style.borderColor = "var(--border)"; e.target.style.boxShadow = "none"; }}
      >
        <option value="">{placeholder}</option>
        {options.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
      <IcChevDown c="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2" style={{ color: "var(--text-muted)" }} />
    </div>
  );
}

/* ─── PartSelectField ────────────────────────────────────────────────────────── */

function PartSelectField({ value, onChange }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const wrapRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const onDown = e => { if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  useEffect(() => { if (open) setTimeout(() => inputRef.current?.focus(), 30); }, [open]);

  const q = query.trim().toLowerCase();
  const filtered = q ? PARTS.filter(p => p.toLowerCase().includes(q)) : PARTS;
  const hasMatches = filtered.length > 0;

  function select(name) { onChange(name); setOpen(false); setQuery(""); }
  function clear(e) { e.stopPropagation(); onChange(""); setQuery(""); }

  return (
    <div ref={wrapRef} className="relative flex-[2] min-w-[150px]">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="flex h-11 w-full items-center justify-between rounded-[8px] px-4 text-sm focus:outline-none"
        style={{
          background: "var(--bg-elevated)",
          border: `1px solid ${open ? "var(--primary)" : "var(--border)"}`,
          boxShadow: open ? "0 0 0 3px var(--primary-muted)" : "none",
          color: value ? "var(--text-primary)" : "var(--text-muted)",
          fontFamily: "var(--ff-body)",
          transition: "border-color 0.15s, box-shadow 0.15s",
        }}
      >
        <span className="truncate">{value || "Part name (optional)"}</span>
        <span className="flex shrink-0 items-center gap-1 ml-2">
          {value && (
            <span role="button" onClick={clear} className="flex h-4 w-4 items-center justify-center rounded-full" style={{ color: "var(--text-muted)" }}>
              <IcX c="h-3 w-3" />
            </span>
          )}
          <IcChevDown c="h-4 w-4" style={{ color: "var(--text-muted)" }} />
        </span>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className="absolute left-0 right-0 top-[calc(100%+6px)] z-[200] rounded-[12px] shadow-xl overflow-hidden"
            style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}
          >
            <div className="p-2" style={{ borderBottom: "1px solid var(--border-subtle)" }}>
              <div className="relative">
                <IcSearch c="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2" style={{ color: "var(--text-muted)" }} />
                <input
                  ref={inputRef}
                  type="text"
                  placeholder="Search parts…"
                  value={query}
                  onChange={e => { setQuery(e.target.value); setAiName(null); setAiError(false); }}
                  onKeyDown={e => { if (e.key === "Escape") setOpen(false); }}
                  className="h-9 w-full rounded-[8px] pl-8 pr-3 text-sm focus:outline-none"
                  style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", color: "var(--text-primary)", fontFamily: "var(--ff-body)" }}
                />
              </div>
            </div>
            <ul className="max-h-52 overflow-y-auto py-1" role="listbox">
              {hasMatches ? filtered.map(p => (
                <li key={p}>
                  <button
                    type="button"
                    onMouseDown={e => e.preventDefault()}
                    onClick={() => select(p)}
                    className="w-full px-4 py-2 text-left text-sm transition-colors"
                    style={{ color: "var(--text-secondary)", fontFamily: "var(--ff-body)" }}
                    onMouseEnter={e => { e.currentTarget.style.background = "var(--bg-hover)"; e.currentTarget.style.color = "var(--text-primary)"; }}
                    onMouseLeave={e => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--text-secondary)"; }}
                  >
                    {p}
                  </button>
                </li>
              )) : (
                <li className="px-4 py-3 text-sm" style={{ color: "var(--text-muted)" }}>
                  No match — press &ldquo;Find Parts&rdquo; to search anyway.
                </li>
              )}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ─── StepCard ───────────────────────────────────────────────────────────────── */

function StepCard({ Icon, n, title, desc, delay, fromRight = false }) {
  const [ref, inView] = useInView();
  return (
    <div
      ref={ref}
      style={{
        opacity: inView ? 1 : 0,
        transform: inView ? "translateX(0)" : `translateX(${fromRight ? 20 : -20}px)`,
        transition: `opacity 0.6s cubic-bezier(0.22,1,0.36,1) ${delay}ms, transform 0.6s cubic-bezier(0.22,1,0.36,1) ${delay}ms`,
        background: "var(--bg-surface)",
        border: "1px solid var(--border)",
      }}
      className="group flex gap-4 rounded-[12px] p-5 transition-all"
      onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--primary-border-strong)"; e.currentTarget.style.boxShadow = "var(--shadow-sm)"; }}
      onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.boxShadow = "none"; }}
    >
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[8px]"
           style={{ background: "var(--primary-muted)", border: "1px solid rgba(255,92,26,0.2)" }}>
        <Icon c="h-5 w-5" style={{ color: "var(--primary)" }} />
      </div>
      <div>
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-bold" style={{ fontFamily: "var(--ff-mono)", color: "var(--primary)", letterSpacing: "0.06em" }}>{n}</span>
          <h4 className="font-semibold text-sm" style={{ color: "var(--text-primary)", fontFamily: "var(--ff-body)" }}>{title}</h4>
        </div>
        <p className="text-sm leading-relaxed" style={{ color: "var(--text-muted)" }}>{desc}</p>
      </div>
    </div>
  );
}

/* ─── Floating geometric shapes for hero ─────────────────────────────────────── */

function FloatingShapes() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none" aria-hidden>
      {/* Large blurred orange circle */}
      <motion.div
        className="absolute rounded-full"
        style={{ width: 600, height: 600, top: "-20%", right: "-10%", background: "radial-gradient(circle, var(--primary-muted) 0%, transparent 70%)", filter: "blur(40px)" }}
        animate={{ scale: [1, 1.1, 1], opacity: [0.6, 0.8, 0.6] }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
      />
      {/* Small violet accent */}
      <motion.div
        className="absolute rounded-full"
        style={{ width: 400, height: 400, bottom: "5%", left: "-5%", background: "radial-gradient(circle, var(--accent-muted) 0%, transparent 70%)", filter: "blur(40px)" }}
        animate={{ scale: [1, 1.15, 1], opacity: [0.5, 0.7, 0.5] }}
        transition={{ duration: 10, repeat: Infinity, ease: "easeInOut", delay: 2 }}
      />
      {/* Geometric corner accent */}
      <div className="absolute top-16 right-16 opacity-30 dark:opacity-20" style={{ width: 200, height: 200, color: "var(--primary)" }}>
        <svg viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="100" cy="100" r="90" stroke="currentColor" strokeWidth="1" strokeDasharray="8 8"/>
          <circle cx="100" cy="100" r="60" stroke="currentColor" strokeWidth="1" opacity="0.7"/>
          <circle cx="100" cy="100" r="30" stroke="currentColor" strokeWidth="1" opacity="0.5"/>
        </svg>
      </div>
    </div>
  );
}

/* ─── Page ───────────────────────────────────────────────────────────────────── */

export default function Home() {
  const { user, loading: authLoading } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  const heroRef = useRef(null);
  const { scrollYProgress } = useScroll({ target: heroRef, offset: ["start start", "end start"] });
  const heroY = useTransform(scrollYProgress, [0, 1], ["0%", "30%"]);
  const heroOpacity = useTransform(scrollYProgress, [0, 0.7], [1, 0]);

  const stagger = {
    container: { hidden: {}, show: { transition: { staggerChildren: 0.12 } } },
    item:      { hidden: { opacity: 0, y: 24 }, show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.22,1,0.36,1] } } },
  };

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)" }}>

      {/* ── Navbar ─────────────────────────────────────────────────────────── */}
      <nav
        className="fixed left-0 right-0 top-0 z-[300] transition-all duration-300"
        style={{ background: "var(--nav-bg)", backdropFilter: "blur(16px)", borderBottom: "1px solid var(--border-subtle)" }}
      >
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="relative flex h-8 w-8 items-center justify-center rounded-[8px] overflow-hidden" style={{ background: "var(--primary)" }}>
              <span style={{ fontFamily: "var(--ff-body)", fontWeight: 800, fontSize: 15, color: "#fff" }}>P</span>
            </div>
            <span style={{ fontFamily: "var(--ff-body)", fontWeight: 700, fontSize: 16, letterSpacing: "-0.01em", color: "var(--text-primary)" }}>Partbridge</span>
          </Link>

          {/* Desktop links */}
          <div className="hidden items-center gap-6 md:flex">
            {[["#how-it-works","How It Works"],["#for-sellers","For Sellers"],["#for-buyers","For Buyers"]].map(([href, label]) => (
              <a key={href} href={href} className="text-sm transition-colors duration-150 link-underline"
                 style={{ color: "var(--text-muted)", fontFamily: "var(--ff-body)" }}
                 onMouseEnter={e=>e.currentTarget.style.color="var(--text-primary)"}
                 onMouseLeave={e=>e.currentTarget.style.color="var(--text-muted)"}>{label}</a>
            ))}
          </div>

          {/* Desktop auth */}
          <div className="hidden items-center gap-2 md:flex">
            <ThemeToggle />
            {!authLoading && !user && (
              <>
                <Link href="/login" className="px-4 py-2 text-sm font-medium transition-colors duration-150"
                      style={{ color: "var(--text-muted)", fontFamily: "var(--ff-body)" }}
                      onMouseEnter={e=>e.currentTarget.style.color="var(--text-primary)"}
                      onMouseLeave={e=>e.currentTarget.style.color="var(--text-muted)"}>Log in</Link>
                <Link href="/register" className="btn-forge" style={{ padding: "8px 20px", fontSize: 13 }}>Sign up free</Link>
              </>
            )}
            {user && (
              <>
                <Link href="/cart" className="px-3.5 py-2 text-sm font-medium transition-colors"
                      style={{ color: "var(--text-muted)" }}
                      onMouseEnter={e=>e.currentTarget.style.color="var(--text-primary)"}
                      onMouseLeave={e=>e.currentTarget.style.color="var(--text-muted)"}>Cart</Link>
                <Link href="/dashboard" className="btn-forge" style={{ padding: "8px 20px", fontSize: 13 }}>Dashboard</Link>
              </>
            )}
          </div>

          <div className="flex items-center gap-1.5 md:hidden">
            <ThemeToggle />
            <button onClick={() => setMobileOpen(o => !o)} className="rounded-[8px] p-2" style={{ color: "var(--text-muted)" }} aria-label="Toggle menu">
              {mobileOpen ? <IcX c="h-5 w-5" /> : <IcMenu c="h-5 w-5" />}
            </button>
          </div>
        </div>

        <AnimatePresence>
          {mobileOpen && (
            <motion.div
              initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2 }}
              className="md:hidden p-4"
              style={{ background: "var(--bg-base)", borderTop: "1px solid var(--border-subtle)" }}
            >
              <div className="flex flex-col gap-2">
                {[["#how-it-works","How It Works"],["#for-sellers","For Sellers"],["#for-buyers","For Buyers"]].map(([href, label]) => (
                  <a key={href} href={href} className="rounded-[8px] px-3 py-2 text-sm" style={{ color: "var(--text-secondary)" }} onClick={() => setMobileOpen(false)}>{label}</a>
                ))}
                {!authLoading && !user && (
                  <>
                    <Link href="/login" className="px-3 py-2 text-sm" style={{ color: "var(--text-secondary)" }}>Log in</Link>
                    <Link href="/register" className="btn-forge justify-center">Sign up free</Link>
                  </>
                )}
                {user && <Link href="/dashboard" className="btn-forge justify-center">Dashboard</Link>}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </nav>

      {/* ── Hero ───────────────────────────────────────────────────────────── */}
      <section ref={heroRef} className="relative flex min-h-[95vh] items-center justify-center overflow-hidden pt-16">
        {/* Parallax background */}
        <motion.div className="absolute inset-0" style={{ y: heroY }}>
          <Image src="/hero.jpeg" alt="" fill className="object-cover" style={{ opacity: 0.15 }} sizes="100vw" priority />
          <div
            className="absolute inset-0"
            style={{
              background:
                "linear-gradient(to bottom, color-mix(in srgb, var(--bg-base) 45%, transparent) 0%, color-mix(in srgb, var(--bg-base) 88%, transparent) 55%, var(--bg-base) 100%)",
            }}
          />
        </motion.div>

        {/* Grid pattern overlay */}
        <div className="absolute inset-0 grid-pattern opacity-20" />

        {/* Floating shapes */}
        <FloatingShapes />

        <motion.div
          className="container relative z-10 mx-auto max-w-5xl px-4 py-20 text-center sm:px-6 lg:px-8"
          style={{ opacity: heroOpacity }}
        >
          {/* Stagger reveal */}
          <motion.div
            variants={stagger.container}
            initial="hidden"
            animate="show"
          >
            {/* Label badge */}
            <motion.div variants={stagger.item}>
              <span className="mb-5 inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-xs font-bold uppercase tracking-[0.12em]"
                    style={{ background: "var(--primary-muted)", border: "1px solid var(--primary-border-soft)", color: "var(--primary)", fontFamily: "var(--ff-body)" }}>
                <span className="h-1.5 w-1.5 rounded-full animate-forge-pulse" style={{ background: "var(--primary)" }} />
                The Used Auto Parts Marketplace
              </span>
            </motion.div>

            {/* Headline */}
            <motion.h1
              variants={stagger.item}
              className="mx-auto mt-4 max-w-4xl leading-tight"
              style={{ fontFamily: "var(--ff-body)", fontWeight: 700, fontSize: "clamp(34px, 5.5vw, 56px)", letterSpacing: "-0.03em", color: "var(--text-primary)", lineHeight: 1.08 }}
            >
              Every Part Has a Price.{" "}
              <span style={{ color: "var(--primary)" }}>
                Every Part Has a Buyer.
              </span>
            </motion.h1>

            {/* Sub */}
            <motion.p
              variants={stagger.item}
              className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed"
              style={{ color: "var(--text-secondary)", fontFamily: "var(--ff-body)" }}
            >
              List your car in minutes — see what every part is worth. Find the exact used part you need
              with verified condition and transparent shipping.
            </motion.p>

            <HomeCarHero stagger={stagger} />

            {/* Stats */}
            <motion.div variants={stagger.item} className="mx-auto mt-14 flex flex-wrap items-center justify-center gap-12">
              {STATS.map((s, i) => (
                <Reveal key={s.label} delay={i * 100}>
                  <div className="text-center">
                    <div className="text-3xl font-bold tabular-nums" style={{ fontFamily: "var(--ff-body)", color: "var(--primary)", letterSpacing: "-0.03em" }}>{s.value}</div>
                    <div className="mt-1 text-xs uppercase tracking-widest" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-body)" }}>{s.label}</div>
                  </div>
                </Reveal>
              ))}
            </motion.div>
          </motion.div>
        </motion.div>

        {/* Scroll indicator */}
        <motion.div
          className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1.5, duration: 0.6 }}
        >
          <span className="text-[10px] uppercase tracking-widest" style={{ color: "var(--text-disabled)", fontFamily: "var(--ff-body)" }}>Scroll</span>
          <motion.div
            className="w-px h-8 rounded-full"
            style={{ background: "linear-gradient(to bottom, var(--primary), transparent)" }}
            animate={{ scaleY: [1, 0.5, 1], opacity: [0.8, 0.3, 0.8] }}
            transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
          />
        </motion.div>
      </section>

      <FeaturedCategories />
      <RecentParts />
      <MakeStrip />
      <HowItWorksBuyer />

      {/* ── How It Works (sellers + legacy buyers) ─────────────────────────── */}
      <section id="for-sellers" className="py-28 relative">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <Reveal className="text-center mb-16">
            <span className="section-label justify-center mb-4">Simple for Everyone</span>
            <h2 className="heading-display text-4xl sm:text-5xl mt-2">How Partbridge Works</h2>
          </Reveal>

          <div className="grid gap-16 lg:grid-cols-2">
            {/* Sellers */}
            <div id="for-sellers">
              <Reveal className="mb-8">
                <div className="flex items-center gap-3">
                  <div className="h-px flex-1" style={{ background: "linear-gradient(to right, var(--primary), transparent)" }} />
                  <h3 className="text-sm font-bold uppercase tracking-widest" style={{ fontFamily: "var(--ff-body)", color: "var(--primary)" }}>For Sellers</h3>
                  <div className="h-px flex-1" style={{ background: "linear-gradient(to left, var(--primary), transparent)" }} />
                </div>
              </Reveal>
              <div className="space-y-3">
                {SELLER_STEPS.map((s, i) => (
                  <div key={s.n}
                    className="group flex gap-4 rounded-[12px] p-5 transition-all duration-200"
                    style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
                    onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--primary-border-strong)"; }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--border)"; }}
                  >
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[8px] transition-colors"
                         style={{ background: "var(--primary-muted)", border: "1px solid var(--primary-border-soft)" }}
                         onMouseEnter={e => { e.currentTarget.style.background = "color-mix(in srgb, var(--primary) 22%, var(--bg-surface))"; }}
                         onMouseLeave={e => { e.currentTarget.style.background = "var(--primary-muted)"; }}>
                      <s.Icon c="h-5 w-5" style={{ color: "var(--primary)" }} />
                    </div>
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-bold" style={{ fontFamily: "var(--ff-mono)", color: "var(--primary)" }}>{s.n}</span>
                        <h4 className="text-sm font-semibold" style={{ fontFamily: "var(--ff-body)", color: "var(--text-primary)" }}>{s.title}</h4>
                      </div>
                      <p className="text-sm leading-relaxed" style={{ color: "var(--text-muted)" }}>{s.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Buyers */}
            <div id="for-buyers">
              <Reveal className="mb-8">
                <div className="flex items-center gap-3">
                  <div className="h-px flex-1" style={{ background: "linear-gradient(to right, var(--accent), transparent)" }} />
                  <h3 className="text-sm font-bold uppercase tracking-widest" style={{ fontFamily: "var(--ff-body)", color: "var(--accent)" }}>For Buyers</h3>
                  <div className="h-px flex-1" style={{ background: "linear-gradient(to left, var(--accent), transparent)" }} />
                </div>
              </Reveal>
              <div className="space-y-3">
                {BUYER_STEPS.map((s, i) => (
                  <div key={s.n}
                    className="group flex gap-4 rounded-[12px] p-5 transition-all duration-200"
                    style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
                    onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--accent-border-strong)"; }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--border)"; }}
                  >
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[8px]"
                         style={{ background: "var(--accent-muted)", border: "1px solid var(--accent-border-soft)" }}>
                      <s.Icon c="h-5 w-5" style={{ color: "var(--accent)" }} />
                    </div>
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-bold" style={{ fontFamily: "var(--ff-mono)", color: "var(--accent)" }}>{s.n}</span>
                        <h4 className="text-sm font-semibold" style={{ fontFamily: "var(--ff-body)", color: "var(--text-primary)" }}>{s.title}</h4>
                      </div>
                      <p className="text-sm leading-relaxed" style={{ color: "var(--text-muted)" }}>{s.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Why Partbridge ─────────────────────────────────────────────────── */}
      <section className="py-28 relative overflow-hidden">
        {/* Background accent */}
        <div className="absolute inset-0" style={{ background: "var(--bg-surface)" }} />
        <div className="absolute inset-0 grid-pattern opacity-30" />
        <div className="absolute top-0 left-0 right-0 h-px" style={{ background: "linear-gradient(to right, transparent, var(--border), transparent)" }} />
        <div className="absolute bottom-0 left-0 right-0 h-px" style={{ background: "linear-gradient(to right, transparent, var(--border), transparent)" }} />

        <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <Reveal className="text-center mb-16">
            <span className="section-label justify-center mb-4">Why Partbridge</span>
            <h2 className="heading-display text-4xl sm:text-5xl mt-2">Built for Trust Between Strangers</h2>
            <p className="mx-auto mt-5 max-w-xl text-base leading-relaxed" style={{ color: "var(--text-secondary)" }}>
              Every feature exists to make parts transactions safe, fair, and transparent for regular people.
            </p>
          </Reveal>

          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {VALUE_PROPS.map((v, i) => (
              <Reveal key={v.title} delay={i * 80}>
                <div
                  className="group h-full rounded-[16px] p-6 transition-all duration-200 cursor-default"
                  style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--primary-border-strong)"; e.currentTarget.style.boxShadow = "var(--shadow-md)"; e.currentTarget.style.transform = "translateY(-2px)"; }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.boxShadow = "none"; e.currentTarget.style.transform = "translateY(0)"; }}
                >
                  <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-[10px] transition-all"
                       style={{ background: "var(--primary-muted)", border: "1px solid var(--primary-border-soft)" }}>
                    <v.Icon c="h-6 w-6" style={{ color: "var(--primary)" }} />
                  </div>
                  <h3 className="font-semibold mb-2" style={{ fontFamily: "var(--ff-body)", color: "var(--text-primary)" }}>{v.title}</h3>
                  <p className="text-sm leading-relaxed" style={{ color: "var(--text-muted)" }}>{v.desc}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ─────────────────────────────────────────────────────────────── */}
      <section className="py-28 relative overflow-hidden">
        <div className="absolute inset-0 mesh-bg" />
        <div className="absolute inset-0 grid-pattern opacity-20" />
        <div className="absolute top-0 left-0 right-0 h-px" style={{ background: "linear-gradient(to right, transparent, var(--border), transparent)" }} />

        <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <Reveal className="mx-auto max-w-2xl text-center">
            <span className="section-label justify-center mb-6">Start Now</span>
            <h2 className="heading-display text-4xl sm:text-5xl">
              Got a Car to Part Out?{" "}
              <span style={{ color: "var(--primary)" }}>
                Start in 60 Seconds.
              </span>
            </h2>
            <p className="mt-5 text-lg leading-relaxed" style={{ color: "var(--text-secondary)" }}>
              Enter your VIN, see what every part is worth, and start selling.
              No business license. No complicated setup.
            </p>

            <div className="mt-10 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
              <Link
                href={user ? "/vehicles/new" : "/register"}
                className="btn-forge gap-2"
                style={{ padding: "14px 32px", fontSize: 15 }}
              >
                List Your Vehicle <IcArrow c="h-4 w-4" />
              </Link>
              <Link
                href="/search"
                className="btn-ghost"
                style={{ padding: "13px 32px", fontSize: 15 }}
              >
                Browse Parts
              </Link>
            </div>

            <div className="mt-10 flex flex-wrap justify-center gap-x-8 gap-y-3">
              {["Free to list", "No monthly fees", "Pay only when you sell"].map(item => (
                <span key={item} className="flex items-center gap-2 text-sm" style={{ color: "var(--text-muted)", fontFamily: "var(--ff-body)" }}>
                  <IcCheck c="h-3.5 w-3.5" style={{ color: "var(--success)" }} />
                  {item}
                </span>
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      {/* ── Footer ──────────────────────────────────────────────────────────── */}
      <footer className="py-12" style={{ borderTop: "1px solid var(--border-subtle)", background: "var(--bg-surface)" }}>
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col items-center justify-between gap-6 sm:flex-row">
            <Link href="/" className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-[6px]" style={{ background: "var(--primary)" }}>
                <span style={{ fontFamily: "var(--ff-body)", fontWeight: 800, fontSize: 12, color: "#fff" }}>P</span>
              </div>
              <span className="text-sm font-bold tracking-tight" style={{ fontFamily: "var(--ff-body)", color: "var(--text-primary)" }}>Partbridge</span>
            </Link>

            <nav className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2">
              {[["Browse","/search"],["Sign in","/login"],["Register","/register"]].map(([label, href]) => (
                <Link key={href} href={href} className="text-sm transition-colors link-underline"
                      style={{ color: "var(--text-muted)", fontFamily: "var(--ff-body)" }}
                      onMouseEnter={e=>e.currentTarget.style.color="var(--text-secondary)"}
                      onMouseLeave={e=>e.currentTarget.style.color="var(--text-muted)"}>{label}</Link>
              ))}
            </nav>

            <p className="text-xs" style={{ color: "var(--text-disabled)", fontFamily: "var(--ff-body)" }}>© 2026 Partbridge</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
