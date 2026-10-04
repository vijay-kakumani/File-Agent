/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        charcoal: {
          950: '#111215',
          900: '#16171b',
          850: '#191b1f',
          800: '#1e2025',
          750: '#23262c',
          700: '#2a2d35',
          600: '#3a3e49',
        }
      }
    },
  },
  plugins: [],
}
