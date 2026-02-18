/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        'accent-copper': '#D4781C',
        'deep-charcoal': '#0B0C0E',
        'terminal-panel': '#121417',
        'surface': 'rgba(255, 255, 255, 0.02)',
        'border-copper': 'rgba(212, 120, 28, 0.2)',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        display: ['Outfit', 'sans-serif'],
        mono: ['ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
}
