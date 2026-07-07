/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#070b10",
        panel: "#0d131c",
        panel2: "#111a25",
        line: "#243244",
        muted: "#91a0b6",
        text: "#e8eef7",
        cyan: "#7f8d9e",
        green: "#2dd47f",
        red: "#ff5c7a",
        amber: "#f6b44b",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
  plugins: [],
};
