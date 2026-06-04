"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { AnimatePresence, motion } from "framer-motion";

const ToastContext = createContext(null);

const VARIANT_STYLES = {
  success: {
    background: "rgba(34,197,94,0.14)",
    border: "1px solid rgba(34,197,94,0.3)",
    color: "#4ade80",
  },
  error: {
    background: "rgba(239,68,68,0.12)",
    border: "1px solid rgba(239,68,68,0.28)",
    color: "var(--danger)",
  },
  warning: {
    background: "rgba(245,158,11,0.12)",
    border: "1px solid rgba(245,158,11,0.28)",
    color: "#fbbf24",
  },
};

function makeId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const timers = useRef(new Map());

  const dismiss = useCallback((id) => {
    const t = timers.current.get(id);
    if (t) clearTimeout(t);
    timers.current.delete(id);
    setToasts((prev) => prev.filter((x) => x.id !== id));
  }, []);

  const show = useCallback(
    (message, variant = "error", durationMs) => {
      const id = makeId();
      const defaultDuration = variant === "error" ? 9000 : 5500;
      const ms = durationMs ?? defaultDuration;
      setToasts((prev) => [...prev, { id, message, variant }]);
      const timer = setTimeout(() => dismiss(id), ms);
      timers.current.set(id, timer);
      return id;
    },
    [dismiss]
  );

  useEffect(
    () => () => {
      timers.current.forEach((t) => clearTimeout(t));
      timers.current.clear();
    },
    []
  );

  const value = useMemo(
    () => ({
      show,
      success: (message, durationMs) => show(message, "success", durationMs),
      error: (message, durationMs) => show(message, "error", durationMs),
      warning: (message, durationMs) => show(message, "warning", durationMs),
      dismiss,
    }),
    [dismiss, show]
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        style={{
          position: "fixed",
          bottom: 20,
          right: 20,
          zIndex: 9999,
          display: "flex",
          flexDirection: "column",
          alignItems: "flex-end",
          gap: 6,
          pointerEvents: "none",
          maxWidth: "min(20rem, calc(100vw - 1.5rem))",
        }}
      >
        <AnimatePresence mode="popLayout">
          {toasts.map((toast) => {
            const style = VARIANT_STYLES[toast.variant] || VARIANT_STYLES.error;
            return (
              <motion.div
                key={toast.id}
                layout
                role="alert"
                initial={{ opacity: 0, x: 20, y: 6 }}
                animate={{ opacity: 1, x: 0, y: 0 }}
                exit={{ opacity: 0, x: 12, transition: { duration: 0.18 } }}
                transition={{ type: "spring", stiffness: 420, damping: 30 }}
                className="pointer-events-auto w-max max-w-[min(20rem,calc(100vw-1.5rem))] rounded-lg px-3 py-2 text-xs leading-snug shadow-lg"
                style={{
                  ...style,
                  fontFamily: "var(--ff-body)",
                  backdropFilter: "blur(8px)",
                }}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 max-w-[16.5rem] break-words" style={{ color: style.color }}>
                    {toast.message}
                  </div>
                  <button
                    type="button"
                    onClick={() => dismiss(toast.id)}
                    className="shrink-0 rounded-md px-1.5 py-0.5 text-base leading-none opacity-70 transition hover:opacity-100"
                    style={{ color: style.color }}
                    aria-label="Dismiss notification"
                  >
                    ×
                  </button>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return ctx;
}
