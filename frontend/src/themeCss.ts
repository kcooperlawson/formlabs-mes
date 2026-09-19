import { PALETTES, type Palette } from './palettes'

function hexToRgba(hex: string, alpha: number): string {
  const h = hex.replace('#', '')
  const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h
  const r = parseInt(full.slice(0, 2), 16)
  const g = parseInt(full.slice(2, 4), 16)
  const b = parseInt(full.slice(4, 6), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

// One palette's tokens as CSS custom-property declarations - ported from
// theme_engine.py's build(), minus the Streamlit-selector CSS (there is no
// [data-testid=...] here to target): the "flair" ask becomes --fl-shadow /
// --fl-shadow-hover, a vivid neon glow for palettes with glow:true and a
// plain elevation shadow otherwise, so buttons and the active nav item pick
// up the theme's own personality without every component needing its own
// per-theme rule.
function paletteDeclarations(p: Palette): string {
  const shadow = p.glow
    ? `0 0 10px ${hexToRgba(p.accent, 0.5)}`
    : `0 2px 6px ${hexToRgba('#000000', p.light ? 0.12 : 0.35)}`
  const shadowHover = p.glow
    ? `0 0 22px ${hexToRgba(p.accent2, 0.85)}`
    : `0 4px 12px ${hexToRgba(p.accent, 0.35)}`
  // A plain hover/active wash independent of the accent colour - white on a
  // dark ground, ink-tinted (dark) on a light one. bg-white/10-style
  // Tailwind opacity utilities assume the first case; a light palette with
  // that same white wash would be nearly invisible on Daylight or Paper
  // White, so every spot that used to hardcode white/N reads this instead.
  const overlayBase = p.light ? p.ink : '#FFFFFF'
  // 72% opaque + a light backdrop-blur (see OperatorFormPage's card) is what
  // lets a glow theme's flourish actually read behind a card tall enough to
  // fill the whole page. Went through 86% first - technically translucent,
  // but the flourish's own lines are already thin and low-alpha (deliberately
  // subtle at full opacity against the plain ground colour), and blurring
  // them further behind a nearly-opaque card diluted them to invisible.
  return `
    --fl-ground: ${p.ground};
    --fl-surface: ${p.surface};
    --fl-surface-glass: ${hexToRgba(p.surface, 0.72)};
    --fl-raised: ${p.raised};
    --fl-border: ${p.line};
    --fl-ink: ${p.ink};
    --fl-body: ${p.body};
    --fl-muted: ${p.muted};
    --fl-accent: ${p.accent};
    --fl-accent-2: ${p.accent2};
    --fl-accent-wash: ${hexToRgba(p.accent, 0.15)};
    --fl-font: ${p.font};
    --fl-shadow: ${shadow};
    --fl-shadow-hover: ${shadowHover};
    --fl-selection: ${hexToRgba(p.accent, 0.35)};
    --fl-overlay-weak: ${hexToRgba(overlayBase, p.light ? 0.05 : 0.05)};
    --fl-overlay: ${hexToRgba(overlayBase, p.light ? 0.08 : 0.1)};
    --fl-overlay-strong: ${hexToRgba(overlayBase, p.light ? 0.14 : 0.15)};
    color-scheme: ${p.light ? 'light' : 'dark'};`
}

// The default lives on bare :root (so an account with no preference, or the
// pre-login screens, sees today's Formlabs Forge with zero lookup), and
// every other palette overrides it under [data-theme="slug"] on <html> -
// see ThemeRoot.tsx, which sets that attribute from the signed-in user's
// preferred_theme.
export function buildThemeStylesheet(): string {
  const [def, ...rest] = PALETTES
  const blocks = [
    `:root {${paletteDeclarations(def)}\n  }`,
    ...rest.map((p) => `:root[data-theme="${p.slug}"] {${paletteDeclarations(p)}\n  }`),
  ]
  return blocks.join('\n\n')
}
