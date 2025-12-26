/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'dark-navy': '#0C1018',
        'navy': '#1A1F27',
        'card-gray': '#1A1F27',
        'charcoal': '#343a40',
        'border-gray': '#2D3542',
        'gold': '#D4A64A',
        'light-gold': '#E7C776',
        'deep-red': '#A03333',
        'light-red': '#CC4A45',
        'off-white': '#F3F2ED',
        'muted-text': '#8B97A7',
        'light-gray': '#adb5bd',
        'neon-green': '#4CAF50',
        'vibrant-yellow': '#FFEB3B',
        'bold-red': '#F52D2D',
        // Legacy aliases for gradual migration
        'electric-blue': '#D4A64A',
      },
      fontFamily: {
        sans: ['Roboto', 'sans-serif'],
        teko: ['Teko', 'sans-serif'],
      },
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'fade-in': {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        'slide-up': {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in': {
          '0%': { transform: 'scaleX(0)', transformOrigin: 'left' },
          '100%': { transform: 'scaleX(1)', transformOrigin: 'left' },
        },
        'pulse-glow': {
          '0%, 100%': { boxShadow: '0 0 5px rgba(212, 166, 74, 0.5)' },
          '50%': { boxShadow: '0 0 20px rgba(212, 166, 74, 0.8)' },
        },
      },
      animation: {
        shimmer: 'shimmer 2s ease-in-out infinite',
        'fade-in': 'fade-in 0.3s ease-out',
        'slide-up': 'slide-up 0.3s ease-out',
        'slide-in': 'slide-in 0.2s ease-out',
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
