import type { Config } from 'tailwindcss'

export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: { border: 'hsl(var(--border))', background: 'hsl(var(--background))', foreground: 'hsl(var(--foreground))', muted: 'hsl(var(--muted))', card: 'hsl(var(--card))', primary: 'hsl(var(--primary))' },
      borderRadius: { xl: '0.85rem' },
      fontFamily: { sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'] },
    },
  },
  plugins: [require('tailwindcss-animate')],
} satisfies Config
