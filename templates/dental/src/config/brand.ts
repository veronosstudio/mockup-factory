/**
 * ─────────────────────────────────────────────────────────────────────────────
 * BRAND CONFIGURATION
 * ─────────────────────────────────────────────────────────────────────────────
 * Single file to edit when adapting the theme for a new client.
 *
 * Colors flow into  → src/styles/theme.css  (CSS custom properties)
 * Fonts flow into   → astro.config.mjs      (Astro 6 built-in font optimizer)
 * Meta flows into   → src/layouts/BaseLayout.astro
 *
 * Color format: use hex (#1a1a2e) or CSS color values.
 * ─────────────────────────────────────────────────────────────────────────────
 */

export const brand = {
  // ── Site Identity ──────────────────────────────────────────────────────────
  name: 'Maple Ridge Dental',
  tagline: 'Gentle dental care for the whole family.',
  description:
    'Checkups, cleanings and cosmetic dentistry in Calgary. New patients welcome, with evening and Saturday appointments and direct billing to your insurance.',
  url: 'https://preview.veronosstudio.com/templates/dental/',
  locale: 'en_CA',

  // ── Fonts ──────────────────────────────────────────────────────────────────
  // To swap fonts: change the `name` values here AND update astro.config.mjs
  // to match (both must stay in sync so Astro can optimise the correct files).
  fonts: {
    body: 'Inter',
    display: 'Plus Jakarta Sans',
  },

  // ── Colour Palette ─────────────────────────────────────────────────────────
  // These values are written to CSS custom properties in theme.css.
  // Tailwind v4 @theme picks them up automatically.
  colors: {
    primary:      '#0B3B47',
    primaryLight: '#0E7C86',
    primaryFg:    '#ffffff',

    accent:       '#0F766E',
    accentFg:     '#ffffff',

    background:   '#ffffff',
    surface:      '#F3F8F8',
    border:       '#DCE8E8',

    text:         '#0B1F24',
    textMuted:    '#4A5D62',

    dark:         '#0B2A31',
    darkSurface:  '#12404A',
  },

  // ── Border radius ──────────────────────────────────────────────────────────
  radius: {
    sm:   '0.375rem',
    md:   '0.625rem',
    lg:   '1rem',
    full: '9999px',
  },
} as const;

export type Brand = typeof brand;
