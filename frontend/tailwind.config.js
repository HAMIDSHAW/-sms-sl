/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#10131A',
        inkraised: '#171B26',
        paper: '#F7F4EC',
        papershade: '#EDE8DA',
        leaf: '#1EB53A',
        leafdeep: '#158A2C',
        sky: '#4DA3F0',
        skydeep: '#155FA6',
        marigold: '#F2A93B',
        slate: '#9AA6B8',
        rule: '#262C3B',
        rulelight: '#DCD5C2',
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'sans-serif'],
        body: ['"Inter"', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      backgroundImage: {
        'ruled': 'repeating-linear-gradient(to bottom, transparent, transparent 27px, rgba(75,85,103,0.08) 28px)',
        'ruled-light': 'repeating-linear-gradient(to bottom, transparent, transparent 27px, rgba(75,85,103,0.12) 28px)',
      },
      boxShadow: {
        card: '0 1px 2px rgba(16,19,26,0.06), 0 8px 24px -12px rgba(16,19,26,0.25)',
        glow: '0 0 60px -10px rgba(30,181,58,0.35)',
      },
      borderRadius: {
        card: '14px',
      },
    },
  },
  plugins: [],
}
