/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#1777FF",
          50: "#EBF3FF",
          100: "#D6E7FF",
          500: "#1777FF",
          600: "#0F62E0",
          700: "#0B4FB8",
        },
        ink: {
          DEFAULT: "#0F172A",
          soft: "#1F1F1F",
          muted: "#64748B",
        },
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "PingFang SC",
          "Hiragino Sans GB",
          "Microsoft YaHei",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
      boxShadow: {
        card: "0 4px 20px -4px rgba(0,0,0,0.08)",
        cardHover: "0 12px 32px -8px rgba(23,119,255,0.22)",
        glow: "0 10px 40px -10px rgba(23,119,255,0.5)",
      },
      borderRadius: {
        xl2: "1.25rem",
      },
      keyframes: {
        floaty: {
          "0%,100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-10px)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        floaty: "floaty 6s ease-in-out infinite",
        shimmer: "shimmer 1.5s infinite",
      },
    },
  },
  plugins: [],
};
