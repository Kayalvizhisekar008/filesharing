/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './core/templates/**/*.html',
    './teacher/templates/**/*.html',
    './student/templates/**/*.html',
  ],
  theme: {
    extend: {
      colors: {
        primary: '#1e40af',
        secondary: '#3b82f6',
      }
    },
  },
  plugins: [],
}