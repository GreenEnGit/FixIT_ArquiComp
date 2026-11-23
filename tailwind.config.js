/** Tailwind CSS 3.4 — compilado a static/tailwind.css con infra/scripts/build_css.sh.
 *  La app es 100% offline: el CSS se genera una vez y se versiona. */
module.exports = {
  content: [
    './templates/**/*.html',
    './static/js/**/*.js',
    './static/flowbite.min.js',
    './routers/**/*.py',
    './main.py',
  ],
  theme: {
    extend: {
      colors: {
        brand: { 50: '#eef2ff', 100: '#e0e7ff', 200: '#c7d2fe', 300: '#a5b4fc', 400: '#818cf8', 500: '#6366f1', 600: '#4f46e5', 700: '#4338ca', 800: '#3730a3', 900: '#312e81' },
      },
      fontFamily: {
        sans: ['ui-sans-serif', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
};
