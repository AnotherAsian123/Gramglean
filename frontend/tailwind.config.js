/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Instagram-inspired surface palette.
        ink: {
          950: "#000000",
          900: "#0a0a0a",
          850: "#121212",
          800: "#1a1a1a",
          700: "#262626",
          600: "#363636",
        },
        ig: {
          blue: "#405DE6",
          indigo: "#5851DB",
          purple: "#833AB4",
          magenta: "#C13584",
          pink: "#E1306C",
          red: "#FD1D1D",
          orange: "#F77737",
          yellow: "#FCAF45",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica",
          "Arial",
          "sans-serif",
        ],
      },
      boxShadow: {
        glow: "0 0 30px -8px rgba(193, 53, 132, 0.55)",
      },
      keyframes: {
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        shimmer: "shimmer 1.6s infinite",
      },
    },
  },
  plugins: [],
};
