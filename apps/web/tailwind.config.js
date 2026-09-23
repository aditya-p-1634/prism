/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/features/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        prism: {
          dark: "#0b0f19",
          panel: "#111827",
          border: "#1f2937",
          accent: "#3b82f6",
          hazard: "#ef4444",
          safe: "#10b981",
          warning: "#f59e0b"
        }
      }
    }
  },
  plugins: []
};
