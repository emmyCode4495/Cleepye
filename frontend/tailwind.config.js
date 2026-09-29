/** @type {import('tailwindcss').Config} */
const c = (v) => `rgb(var(--${v}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: c("ink"), 1: c("ink-1"), 2: c("ink-2"), 3: c("ink-3") },
        bone: c("bone"),
        muted: c("muted"),
        dim: c("dim"),
        lime: { DEFAULT: c("lime"), ink: c("lime-ink") },
        amber: { DEFAULT: c("amber") },
        coral: { DEFAULT: c("coral") },
      },
      fontFamily: {
        display: ['"Bricolage Grotesque Variable"', "system-ui", "sans-serif"],
        sans: ['"Geist Variable"', "system-ui", "-apple-system", "sans-serif"],
        mono: ['"Geist Mono Variable"', "ui-monospace", "SFMono-Regular", "monospace"],
      },
      borderColor: { DEFAULT: "rgb(255 255 255 / 0.08)" },
      boxShadow: {
        glow: "0 0 0 1px rgb(var(--lime) / 0.35), 0 8px 40px -8px rgb(var(--lime) / 0.35)",
        card: "0 1px 0 rgb(255 255 255 / 0.04) inset, 0 12px 32px -16px rgb(0 0 0 / 0.8)",
      },
      keyframes: {
        rise: {
          from: { opacity: "0", transform: "translateY(10px)" },
          to: { opacity: "1", transform: "none" },
        },
        sweep: {
          "0%": { transform: "translateX(-10%)" },
          "100%": { transform: "translateX(110%)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        pulseDot: {
          "0%,100%": { opacity: "1" },
          "50%": { opacity: "0.35" },
        },
        toastIn: {
          from: { opacity: "0", transform: "translateY(8px) scale(.98)" },
          to: { opacity: "1", transform: "none" },
        },
      },
      animation: {
        rise: "rise .55s cubic-bezier(.2,.7,.2,1) both",
        sweep: "sweep 2.4s cubic-bezier(.5,0,.5,1) infinite",
        shimmer: "shimmer 1.8s linear infinite",
        "pulse-dot": "pulseDot 1.6s ease-in-out infinite",
        "toast-in": "toastIn .25s ease-out both",
      },
    },
  },
  plugins: [],
};
