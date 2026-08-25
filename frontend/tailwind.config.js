/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Gramglean palette (STYLE.md) with tint/shade variants.
        carbon: {
          DEFAULT: "#191716",
          500: "#3b3735",
          600: "#2e2b29",
          700: "#242120",
          800: "#1d1b1a",
          900: "#191716",
          950: "#121010",
        },
        mahogany: {
          DEFAULT: "#440D0F",
          300: "#c4787b",
          400: "#9c3b3f",
          500: "#6d181b",
          600: "#571114",
          700: "#440D0F",
          800: "#320809",
          900: "#210506",
        },
        mauve: {
          DEFAULT: "#603A40",
          300: "#a97f87",
          400: "#83565e",
          500: "#70464d",
          600: "#603A40",
          700: "#4d2e33",
          800: "#3a2226",
          900: "#28171a",
        },
        thistle: {
          DEFAULT: "#BEB2C8",
          100: "#efecf3",
          200: "#d8d0df",
          300: "#BEB2C8",
          400: "#a294b0",
          500: "#877797",
          600: "#6c5e7b",
          700: "#54485f",
        },
        rose: {
          DEFAULT: "#84596B",
          200: "#d3b8c3",
          300: "#b58fa0",
          400: "#9c7183",
          500: "#84596B",
          600: "#6c4757",
          700: "#543744",
          800: "#3d2732",
        },
      },
      fontFamily: {
        sans: [
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
      boxShadow: {
        glow: "0 0 40px -10px rgba(132, 89, 107, 0.6)",
      },
    },
  },
  plugins: [],
};
