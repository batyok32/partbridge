"use client";

import { useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";
import { PARTS } from "@/lib/parts-data";

const MAX_VISIBLE = 24; // badges shown before filtering

/**
 * Multi-select part picker.
 *
 * Props:
 *   selected  string[]            – currently selected part names
 *   onChange  (string[]) => void  – called on every change
 *   label     string              – optional heading text
 */
export function PartsPickerMulti({ selected = [], onChange, label }) {
  const [query, setQuery] = useState("");
  const [aiName, setAiName] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState(false);

  const q = query.trim().toLowerCase();
  const filtered = q
    ? PARTS.filter((p) => p.toLowerCase().includes(q)).slice(0, MAX_VISIBLE)
    : PARTS.slice(0, MAX_VISIBLE);
  const hasMatches = filtered.length > 0;

  // AI normalize after 600 ms when nothing matches
  useEffect(() => {
    if (!q || hasMatches) {
      setAiName(null);
      setAiError(false);
      return;
    }
    if (aiLoading || aiName) return;
    const t = setTimeout(async () => {
      setAiLoading(true);
      setAiError(false);
      try {
        const data = await apiFetch("/browse/normalize-part/", {
          auth: false,
          method: "POST",
          body: JSON.stringify({ raw_name: query.trim() }),
        });
        setAiName(data.normalized_name || query.trim());
      } catch {
        setAiError(true);
      } finally {
        setAiLoading(false);
      }
    }, 600);
    return () => clearTimeout(t);
  }, [q, hasMatches]); // eslint-disable-line react-hooks/exhaustive-deps

  function toggle(name) {
    if (selected.includes(name)) {
      onChange(selected.filter((x) => x !== name));
    } else {
      onChange([...selected, name]);
    }
  }

  function addAiPart() {
    if (!aiName) return;
    if (!selected.includes(aiName)) onChange([...selected, aiName]);
    setQuery("");
    setAiName(null);
  }

  return (
    <div>
      {label && (
        <p
          className="mb-2 text-xs font-semibold uppercase tracking-wide"
          style={{ color: "var(--text-primary)" }}
        >
          {label}
        </p>
      )}

      {/* Selected chips */}
      {selected.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {selected.map((p) => (
            <span
              key={p}
              className="inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium"
              style={{
                borderColor: "var(--primary-border-soft)",
                background: "var(--primary-muted)",
                color: "var(--primary)",
              }}
            >
              {p}
              <button
                type="button"
                aria-label={`Remove ${p}`}
                onClick={() => toggle(p)}
                className="ml-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full transition-colors"
                style={{ color: "var(--primary-dim)" }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "var(--bg-hover)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "transparent";
                }}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Search input */}
      <input
        type="text"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setAiName(null);
          setAiError(false);
        }}
        placeholder="Search parts…"
        className="input-forge h-9 w-full rounded-lg"
      />

      {/* Part badges */}
      <div className="mt-2 flex max-h-36 flex-wrap gap-1.5 overflow-y-auto">
        {filtered.map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => toggle(p)}
            className="rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors"
            style={
              selected.includes(p)
                ? {
                    borderColor: "var(--primary-border-strong)",
                    background: "var(--primary-muted)",
                    color: "var(--primary)",
                  }
                : {
                    borderColor: "var(--border)",
                    background: "var(--bg-elevated)",
                    color: "var(--text-primary)",
                  }
            }
            onMouseEnter={(e) => {
              if (!selected.includes(p)) {
                e.currentTarget.style.borderColor = "var(--border-strong)";
                e.currentTarget.style.background = "var(--bg-hover)";
              }
            }}
            onMouseLeave={(e) => {
              if (!selected.includes(p)) {
                e.currentTarget.style.borderColor = "var(--border)";
                e.currentTarget.style.background = "var(--bg-elevated)";
              }
            }}
          >
            {p}
          </button>
        ))}
      </div>

      {/* AI suggestion row */}
      {q && !hasMatches && (
        <div className="mt-2">
          {aiName ? (
            <button
              type="button"
              onClick={addAiPart}
              className="flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm font-medium transition-colors"
              style={{
                borderColor: "var(--primary-border-soft)",
                background: "var(--primary-muted)",
                color: "var(--primary)",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = "var(--primary-border-strong)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "var(--primary-border-soft)";
              }}
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth={1.75}
                strokeLinecap="round"
                strokeLinejoin="round"
                className="h-3.5 w-3.5 shrink-0"
                aria-hidden
              >
                <path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z" />
              </svg>
              Add &ldquo;{aiName}&rdquo;
            </button>
          ) : aiLoading ? (
            <div
              className="flex items-center gap-2 px-3 py-2 text-sm"
              style={{ color: "var(--text-secondary)" }}
            >
              <span
                className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2"
                style={{
                  borderColor: "var(--border)",
                  borderTopColor: "var(--primary)",
                }}
              />
              Looking up part…
            </div>
          ) : aiError ? (
            <p className="px-2 py-1 text-xs" style={{ color: "var(--text-muted)" }}>
              No match — type more to refine.
            </p>
          ) : null}
        </div>
      )}
    </div>
  );
}
