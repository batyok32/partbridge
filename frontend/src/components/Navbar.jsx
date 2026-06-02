"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

import { useAuth } from "@/context/auth-context";
import { isApprovedSeller, isBuyerCapable } from "@/lib/roles";
import { ThemeToggle } from "@/components/ThemeToggle";

/* ── Logo mark ─────────────────────────────────────────────────────────────── */
function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2.5 group">
      <div
        className="relative flex h-8 w-8 items-center justify-center rounded-[8px] overflow-hidden"
        style={{ background: "var(--primary)" }}
      >
        <span
          style={{
            fontFamily: "var(--ff-body)",
            fontWeight: 800,
            fontSize: 15,
            color: "#fff",
            letterSpacing: "-0.02em",
          }}
        >
          P
        </span>
        <div
          className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300"
          style={{
            background:
              "linear-gradient(135deg, rgba(255,255,255,0.15) 0%, transparent 60%)",
          }}
        />
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
        Partbridge
      </span>
    </Link>
  );
}

/* ── Nav link ──────────────────────────────────────────────────────────────── */
function NavLink({ href, children, onClick }) {
  const pathname = usePathname();
  const active =
    pathname === href || (href.length > 1 && pathname.startsWith(href));

  return (
    <Link
      href={href}
      onClick={onClick}
      className="relative px-3 py-1.5 text-sm font-medium transition-colors duration-150"
      style={{
        fontFamily: "var(--ff-body)",
        color: active ? "var(--text-primary)" : "var(--text-muted)",
      }}
      onMouseEnter={(e) => {
        if (!active) e.currentTarget.style.color = "var(--text-secondary)";
      }}
      onMouseLeave={(e) => {
        if (!active) e.currentTarget.style.color = "var(--text-muted)";
      }}
    >
      {children}
      {active && (
        <motion.span
          layoutId="nav-indicator"
          className="absolute inset-0 rounded-[8px]"
          style={{
            // background: "var(--bg-elevated)",
            border: "1px solid var(--border)",
          }}
          transition={{ type: "spring", bounce: 0.2, duration: 0.4 }}
        />
      )}
      <span className="relative z-10">{/* content above indicator */}</span>
    </Link>
  );
}

/* ── Main navbar ───────────────────────────────────────────────────────────── */
export function Navbar() {
  const pathname = usePathname();
  const { user, loading } = useAuth();
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Home page has its own hero navbar
  if (pathname === "/") return null;

  const close = () => setOpen(false);
  const isSeller = isApprovedSeller(user);
  const isBuyer = user ? isBuyerCapable(user) : false;

  return (
    <header
      className="sticky top-0 z-[300] transition-all duration-300"
      style={{
        background: scrolled ? "var(--nav-bg-scrolled)" : "var(--nav-bg)",
        backdropFilter: "blur(16px)",
        borderBottom: `1px solid ${scrolled ? "var(--border)" : "var(--border-subtle)"}`,
      }}
    >
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4 sm:px-6">
        <Logo />

        {/* Desktop nav */}
        <nav
          className="hidden flex-1 items-center gap-1 md:flex"
          style={{ position: "relative" }}
        >
          <NavLink href="/browse">Browse Parts</NavLink>
          {user && !isSeller && (
            <NavLink href="/seller/apply">Sell on Partbridge</NavLink>
          )}
          {user && isSeller && <NavLink href="/vehicles">My Vehicles</NavLink>}
          {user && <NavLink href="/inbox">Inbox</NavLink>}
          {user && isBuyer && <NavLink href="/purchases">Purchases</NavLink>}
          {user && isSeller && <NavLink href="/orders">Sales</NavLink>}
          {user && isSeller && <NavLink href="/money">Money</NavLink>}
        </nav>

        {/* Desktop auth */}
        <div className="ml-auto hidden items-center gap-2 md:flex">
          <ThemeToggle />
          {!loading && !user && (
            <>
              <Link
                href="/login"
                className="px-4 py-1.5 text-sm font-medium rounded-[8px] transition-colors duration-150"
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
                Sign in
              </Link>
              <Link
                href="/register"
                className="btn-forge"
                style={{ padding: "7px 18px", fontSize: 13 }}
              >
                Sign up free
              </Link>
            </>
          )}
          {user && (
            <>
              {isBuyer && (
                <Link
                  href="/cart"
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] text-sm font-medium transition-colors duration-150"
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
                  <CartIcon />
                  Cart
                </Link>
              )}
              <Link
                href="/dashboard"
                className="btn-forge"
                style={{ padding: "7px 18px", fontSize: 13 }}
              >
                Dashboard
              </Link>
            </>
          )}
        </div>

        {/* Mobile hamburger */}
        <ThemeToggle className="ml-auto md:ml-0 md:hidden" />
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-label="Toggle menu"
          className="flex h-9 w-9 items-center justify-center rounded-[8px] transition-colors duration-150 md:hidden"
          style={{
            color: "var(--text-muted)",
            background: open ? "var(--bg-elevated)" : "transparent",
          }}
        >
          <AnimatePresence mode="wait" initial={false}>
            {open ? (
              <motion.span
                key="x"
                initial={{ rotate: -90, opacity: 0 }}
                animate={{ rotate: 0, opacity: 1 }}
                exit={{ rotate: 90, opacity: 0 }}
                transition={{ duration: 0.15 }}
              >
                <XIcon />
              </motion.span>
            ) : (
              <motion.span
                key="menu"
                initial={{ rotate: 90, opacity: 0 }}
                animate={{ rotate: 0, opacity: 1 }}
                exit={{ rotate: -90, opacity: 0 }}
                transition={{ duration: 0.15 }}
              >
                <MenuIcon />
              </motion.span>
            )}
          </AnimatePresence>
        </button>
      </div>

      {/* Mobile menu */}
      <AnimatePresence>
        {open && (
          <motion.div
            key="mobile-menu"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="md:hidden"
            style={{
              borderTop: "1px solid var(--border-subtle)",
              background: "var(--bg-base)",
            }}
          >
            <nav className="flex flex-col gap-1 p-4">
              <NavLink href="/browse" onClick={close}>
                Browse Parts
              </NavLink>
              {user && !isSeller && (
                <NavLink href="/seller/apply" onClick={close}>
                  Sell on Partbridge
                </NavLink>
              )}
              {user && isSeller && (
                <NavLink href="/vehicles" onClick={close}>
                  My Vehicles
                </NavLink>
              )}
              {user && (
                <NavLink href="/inbox" onClick={close}>
                  Inbox
                </NavLink>
              )}
              {user && isBuyer && (
                <NavLink href="/purchases" onClick={close}>
                  Purchases
                </NavLink>
              )}
              {user && isSeller && (
                <NavLink href="/orders" onClick={close}>
                  Sales
                </NavLink>
              )}
              {user && isSeller && (
                <NavLink href="/money" onClick={close}>
                  Money
                </NavLink>
              )}

              <div
                className="mt-3 pt-3"
                style={{ borderTop: "1px solid var(--border-subtle)" }}
              >
                {!loading && !user ? (
                  <div className="flex flex-col gap-2">
                    <Link
                      href="/login"
                      onClick={close}
                      className="px-3 py-2 text-sm font-medium rounded-[8px]"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      Sign in
                    </Link>
                    <Link
                      href="/register"
                      onClick={close}
                      className="btn-forge justify-center"
                    >
                      Sign up free
                    </Link>
                  </div>
                ) : user ? (
                  <div className="flex flex-col gap-2">
                    {isBuyer && (
                      <Link
                        href="/cart"
                        onClick={close}
                        className="px-3 py-2 text-sm font-medium"
                        style={{ color: "var(--text-secondary)" }}
                      >
                        Cart
                      </Link>
                    )}
                    <Link
                      href="/dashboard"
                      onClick={close}
                      className="btn-forge justify-center"
                    >
                      Dashboard
                    </Link>
                  </div>
                ) : null}
              </div>
            </nav>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}

/* ── Inline icons ──────────────────────────────────────────────────────────── */
function CartIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4"
      aria-hidden
    >
      <circle cx="9" cy="21" r="1" />
      <circle cx="20" cy="21" r="1" />
      <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
    </svg>
  );
}
function MenuIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-5 w-5"
      aria-hidden
    >
      <path d="M4 6h16M4 12h16M4 18h16" />
    </svg>
  );
}
function XIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-5 w-5"
      aria-hidden
    >
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}
