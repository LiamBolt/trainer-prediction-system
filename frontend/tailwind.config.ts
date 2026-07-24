import type { Config } from 'tailwindcss';
import animate from 'tailwindcss-animate';

/**
 * TPS design tokens — §4.
 * Fixed palette (primary-50..900, semantic, viz) is law (D10).
 * Theme-varying surfaces are backed by CSS custom properties defined in
 * src/styles/globals.css, so a single utility class like `bg-surface` is
 * correct in both light and dark.
 */
const config: Config = {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    // Restrict the radius scale to the four legal steps (§4.4).
    borderRadius: {
      none: '0px',
      sm: '6px',
      DEFAULT: '6px',
      md: '10px',
      lg: '14px',
      full: '9999px',
    },
    extend: {
      colors: {
        // Brand navy scale — fixed hex, identical in both themes (§4.1).
        primary: {
          50: '#f6f6f9',
          100: '#ecebf0',
          200: '#c2c1d0',
          300: '#a2a0b8',
          400: '#8684a2',
          500: '#67648a',
          600: '#534f7a',
          700: '#3f3b6b',
          800: '#26215c',
          900: '#19154e',
        },

        // Theme-varying surface + text tokens (CSS-var backed, alpha-aware).
        canvas: 'rgb(var(--canvas) / <alpha-value>)',
        surface: 'rgb(var(--surface) / <alpha-value>)',
        'surface-raised': 'rgb(var(--surface-raised) / <alpha-value>)',
        'surface-sunken': 'rgb(var(--surface-sunken) / <alpha-value>)',
        ink: 'rgb(var(--ink) / <alpha-value>)',
        'text-secondary': 'rgb(var(--text-secondary) / <alpha-value>)',
        'text-muted': 'rgb(var(--text-muted) / <alpha-value>)',
        'text-disabled': 'rgb(var(--text-disabled) / <alpha-value>)',
        brand: {
          DEFAULT: 'rgb(var(--brand) / <alpha-value>)',
          hover: 'rgb(var(--brand-hover) / <alpha-value>)',
          fg: 'rgb(var(--brand-fg) / <alpha-value>)',
        },

        // Borders with baked-in alpha — referenced directly.
        hairline: 'var(--border-hairline)',
        strong: 'var(--border-strong)',

        // Semantic status colours — fg / bg / border (§4.1).
        success: {
          fg: 'var(--success-fg)',
          bg: 'var(--success-bg)',
          border: 'var(--success-border)',
        },
        warning: {
          fg: 'var(--warning-fg)',
          bg: 'var(--warning-bg)',
          border: 'var(--warning-border)',
        },
        danger: {
          fg: 'var(--danger-fg)',
          bg: 'var(--danger-bg)',
          border: 'var(--danger-border)',
        },
        info: {
          fg: 'var(--info-fg)',
          bg: 'var(--info-bg)',
          border: 'var(--info-border)',
        },

        // Monochromatic indigo data-viz ramp (§4.1) — no rainbows.
        viz: {
          1: 'var(--viz-1)',
          2: 'var(--viz-2)',
          3: 'var(--viz-3)',
          4: 'var(--viz-4)',
          5: 'var(--viz-5)',
        },

        glass: {
          bg: 'var(--glass-bg)',
          border: 'var(--glass-border)',
        },
        overlay: 'var(--overlay)',
        'focus-ring': 'var(--focus-ring)',
      },

      fontFamily: {
        display: ['Roboto', 'system-ui', 'sans-serif'],
        sans: ['"Open Sans"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },

      // Exact type scale — §4.3. [size, { lineHeight, letterSpacing, fontWeight }]
      fontSize: {
        'display-lg': ['40px', { lineHeight: '44px', letterSpacing: '-0.02em', fontWeight: '700' }],
        display: ['32px', { lineHeight: '38px', letterSpacing: '-0.015em', fontWeight: '700' }],
        h1: ['24px', { lineHeight: '30px', letterSpacing: '-0.01em', fontWeight: '700' }],
        h2: ['20px', { lineHeight: '26px', letterSpacing: '-0.005em', fontWeight: '700' }],
        h3: ['16px', { lineHeight: '22px', letterSpacing: '0', fontWeight: '600' }],
        'body-lg': ['15px', { lineHeight: '22px' }],
        body: ['14px', { lineHeight: '20px' }],
        'body-sm': ['13px', { lineHeight: '18px' }],
        caption: ['12px', { lineHeight: '16px', fontWeight: '500' }],
        label: ['11px', { lineHeight: '14px', letterSpacing: '0.08em', fontWeight: '500' }],
        data: ['13px', { lineHeight: '18px' }],
        'data-lg': ['20px', { lineHeight: '24px', letterSpacing: '-0.01em', fontWeight: '600' }],
        'data-xl': ['28px', { lineHeight: '32px', letterSpacing: '-0.02em', fontWeight: '600' }],
      },

      spacing: {
        // Fixed component dimensions — named to avoid arbitrary values (§5.3, §17.4).
        row: '52px', // table row height
        badge: '22px', // badge height
        sidebar: '264px',
        'sidebar-collapsed': '72px',
        'app-bar': '64px',
        classification: '28px',
      },

      maxWidth: {
        content: '1440px',
        form: '680px',
        card: '380px',
      },

      // Named viewport/menu dimensions so screens need no arbitrary values (§17.4).
      height: { dvh: '100dvh' },
      minHeight: { dvh: '100dvh', panel: '60vh' },
      minWidth: { menu: '200px' },

      gridTemplateColumns: {
        // The prediction screen's 62% / 38% split (§11.4), gutter-safe via fr.
        predict: 'minmax(0, 1.63fr) minmax(0, 1fr)',
      },

      boxShadow: {
        // Elevation switches per theme via CSS vars (§4.4).
        e1: 'var(--shadow-e1)',
        e2: 'var(--shadow-e2)',
        e3: 'var(--shadow-e3)',
      },

      transitionTimingFunction: {
        entry: 'cubic-bezier(.2,.8,.2,1)',
        exit: 'cubic-bezier(.4,0,1,1)',
      },

      transitionDuration: {
        micro: '120ms',
        default: '180ms',
        panel: '240ms',
        page: '320ms',
      },

      keyframes: {
        'accordion-down': {
          from: { height: '0' },
          to: { height: 'var(--radix-accordion-content-height)' },
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to: { height: '0' },
        },
        shake: {
          '0%, 100%': { transform: 'translateX(0)' },
          '25%': { transform: 'translateX(-4px)' },
          '75%': { transform: 'translateX(4px)' },
        },
      },
      animation: {
        'accordion-down': 'accordion-down 240ms cubic-bezier(.2,.8,.2,1)',
        'accordion-up': 'accordion-up 240ms cubic-bezier(.4,0,1,1)',
        shake: 'shake 120ms ease-in-out',
      },
    },
  },
  plugins: [animate],
};

export default config;
