/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      /* ── FORGE color tokens ─────────────────────────────────── */
      colors: {
        forge: {
          base: "#ffffff",
          surface: "#f3f4f6",
          elevated: "#ffffff",
          hover: "#e8eaed",
          border: "#d5d9df",
          "border-subtle": "#e8eaed",
          "border-strong": "#b6bbc4",
          orange: "#c7511f",
          "orange-bright": "#e77600",
          "orange-dim": "#a14018",
          "orange-muted": "rgba(199,81,31,0.1)",
          violet: "#007185",
          "violet-dim": "#005c6e",
          "violet-muted": "rgba(0,113,133,0.08)",
          success: "#067d62",
          warning: "#b8860b",
          danger: "#c40000",
          text: "#0f1111",
          "text-secondary": "#565959",
          "text-muted": "#888c8c",
          "text-disabled": "#c9cbcc",
        },
      },

      /* ── Fonts (prefer CSS variables from layout) ─────────── */
      fontFamily: {
        display: ["var(--font-display)", "ui-sans-serif", "system-ui", "sans-serif"],
        body: ["var(--font-body)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },

      /* ── Typography scale ───────────────────────────────────── */
      fontSize: {
        "2xs": ["10px", "1.4"],
        xs:    ["12px", "1.5"],
        sm:    ["13px", "1.5"],
        base:  ["15px", "1.6"],
        md:    ["16px", "1.5"],
        lg:    ["18px", "1.4"],
        xl:    ["20px", "1.3"],
        "2xl": ["24px", "1.25"],
        "3xl": ["30px", "1.2"],
        "4xl": ["36px", "1.1"],
        "5xl": ["48px", "1.05"],
        "6xl": ["60px", "1"],
        "7xl": ["72px", "1"],
      },

      /* ── Spacing scale ──────────────────────────────────────── */
      spacing: {
        4.5:  "18px",
        5.5:  "22px",
        18:   "72px",
        22:   "88px",
        26:   "104px",
        30:   "120px",
      },

      /* ── Border radius ──────────────────────────────────────── */
      borderRadius: {
        sm:  "6px",
        DEFAULT: "10px",
        lg:  "16px",
        xl:  "24px",
        "2xl": "32px",
      },

      /* ── Box shadows ────────────────────────────────────────── */
      boxShadow: {
        sm: "0 1px 2px rgba(15,17,17,0.06)",
        md: "0 2px 8px rgba(15,17,17,0.08)",
        lg: "0 4px 16px rgba(15,17,17,0.1)",
        xl: "0 8px 24px rgba(15,17,17,0.12)",
        forge: "0 2px 8px rgba(199,81,31,0.2)",
        violet: "0 2px 8px rgba(0,113,133,0.12)",
        inset: "inset 0 1px 0 rgba(255,255,255,0.5)",
      },

      /* ── Keyframes ──────────────────────────────────────────── */
      keyframes: {
        "fade-up": {
          "0%":   { opacity: "0", transform: "translateY(20px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          "0%":   { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "slide-right": {
          "0%":   { opacity: "0", transform: "translateX(-16px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        "slide-left": {
          "0%":   { opacity: "0", transform: "translateX(16px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%":      { transform: "translateY(-10px)" },
        },
        "float-slow": {
          "0%, 100%": { transform: "translate(0, 0) rotate(0deg)" },
          "33%":      { transform: "translate(3%, -2%) rotate(1deg)" },
          "66%":      { transform: "translate(-2%, 2%) rotate(-1deg)" },
        },
        "gradient-drift": {
          "0%, 100%": { backgroundPosition: "0% 50%" },
          "50%":      { backgroundPosition: "100% 50%" },
        },
        shimmer: {
          "0%":   { backgroundPosition: "200% center" },
          "100%": { backgroundPosition: "-200% center" },
        },
        pulseGlow: {
          "0%, 100%": { opacity: "0.5", transform: "scale(1)" },
          "50%":      { opacity: "0.8", transform: "scale(1.08)" },
        },
        marquee: {
          "0%":   { transform: "translateX(0)" },
          "100%": { transform: "translateX(-50%)" },
        },
        "spin-slow": {
          "0%":   { transform: "rotate(0deg)" },
          "100%": { transform: "rotate(360deg)" },
        },
        "forge-pulse": {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(199,81,31,0)" },
          "50%": { boxShadow: "0 0 16px 3px rgba(199,81,31,0.22)" },
        },
        "scan-line": {
          "0%":   { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100vh)" },
        },
        "scale-in": {
          "0%":   { opacity: "0", transform: "scale(0.96)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
      },

      /* ── Animation utilities ────────────────────────────────── */
      animation: {
        "fade-up":       "fade-up 0.6s cubic-bezier(0.22, 1, 0.36, 1) both",
        "fade-in":       "fade-in 0.4s ease both",
        "slide-right":   "slide-right 0.5s cubic-bezier(0.22,1,0.36,1) both",
        "slide-left":    "slide-left 0.5s cubic-bezier(0.22,1,0.36,1) both",
        float:           "float 5s ease-in-out infinite",
        "float-slow":    "float-slow 12s ease-in-out infinite",
        "gradient-drift":"gradient-drift 8s ease-in-out infinite",
        shimmer:         "shimmer 4s linear infinite",
        pulseGlow:       "pulseGlow 3s ease-in-out infinite",
        marquee:         "marquee 32s linear infinite",
        "spin-slow":     "spin-slow 20s linear infinite",
        "forge-pulse":   "forge-pulse 2.5s ease-in-out infinite",
        "scan-line":     "scan-line 6s linear infinite",
        "scale-in":      "scale-in 0.3s cubic-bezier(0.22,1,0.36,1) both",
      },

      /* ── Background size ────────────────────────────────────── */
      backgroundSize: {
        "300%": "300%",
      },
    },
  },
  plugins: [],
};
