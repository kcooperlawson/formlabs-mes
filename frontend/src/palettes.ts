// Bringing personalization back, ported from themes.py / theme_engine.py's
// Palette system - a dozen colours plus a couple of style flags describe a
// theme, rather than hand-writing CSS per component per theme (which is how
// the original's first 24 themes were built, and exactly the thing
// theme_engine.py's own docstring says started to bite: "a new component
// has to be styled twenty-four times, and one miss shows up only when
// somebody happens to be on that theme").
//
// Every palette here becomes a `[data-theme="slug"] { --fl-*: ... }` block
// (see themeCss.ts) that frontend/src/theme.ts's `fl` tokens read from, so a
// new theme is a data entry, not a new stylesheet. Curated rather than all
// thirty-four: the ten already-designed Palette themes (light, dark, and
// two built to the accessibility floor - exactly the "readability from
// different distances" need) plus the best-loved of the original
// twenty-four hand-styled ones, including the two asked for by name.
export interface Palette {
  slug: string
  name: string
  ground: string   // page background
  surface: string  // cards, sidebar, inputs
  raised: string   // hover / elevated surface
  line: string      // borders
  ink: string       // headings, strong text
  body: string      // body text
  muted: string     // secondary text, labels
  accent: string    // primary action, active state
  accent2: string   // hover / highlight
  font: string
  light: boolean
  glow: boolean     // neon-style outer glow on hover/focus instead of a plain shadow
  tags: string[]
}

const SANS = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif'
const MONO = '"JetBrains Mono", "Cascadia Code", Consolas, "Courier New", monospace'
const SERIF = 'Georgia, "Iowan Old Style", "Palatino Linotype", serif'

export const PALETTES: Palette[] = [
  // ------------------------------------------------------------- brand/dark
  {
    slug: 'formlabs-forge', name: 'Formlabs Forge',
    ground: '#0F172A', surface: '#1E293B', raised: '#0F172A', line: '#334155',
    ink: '#F8FAFC', body: '#CBD5E1', muted: '#94A3B8',
    // #CD4D0B rather than the brand's own #EA580C: the app's original
    // Streamlit CSS carried a comment fixing exactly this button to CD4D0B
    // because EA580C only reads 3.56:1 against white text, below WCAG AA -
    // applied uniformly here (badges, borders, nav) rather than only on the
    // one control that got noticed.
    accent: '#CD4D0B', accent2: '#F97316',
    font: SANS, light: false, glow: false, tags: ['dark', 'brand', 'default'],
  },
  {
    slug: 'formlabs-onyx', name: 'Formlabs Onyx',
    ground: '#0B0B0C', surface: '#131314', raised: '#1B1B1C', line: '#232324',
    ink: '#FFFFFF', body: '#F2F2F2', muted: '#8A8A8D',
    accent: '#F2F2F2', accent2: '#FFFFFF',
    font: SANS, light: false, glow: false, tags: ['dark', 'monochrome'],
  },
  {
    slug: 'vaporwave-1984', name: 'Vaporwave 1984',
    ground: '#1A0B2E', surface: '#2B1055', raised: '#3A1670', line: '#4A00E0',
    ink: '#FFFFFF', body: '#E0B0FF', muted: '#B389D4',
    accent: '#FF007F', accent2: '#00FFFF',
    font: '"Trebuchet MS", sans-serif', light: false, glow: true, tags: ['dark', 'retro', 'fun'],
  },
  {
    slug: 'synthwave-sunrise', name: 'Synthwave Sunrise',
    ground: '#0F0C29', surface: '#1B1833', raised: '#242042', line: '#302B63',
    ink: '#FFFFFF', body: '#E2E8F0', muted: '#A6A4C2',
    accent: '#FF416C', accent2: '#FF4B2B',
    font: SANS, light: false, glow: true, tags: ['dark', 'retro', 'fun'],
  },
  {
    slug: 'neon-cyberpunk', name: 'Neon Cyberpunk',
    ground: '#090117', surface: '#05000A', raised: '#1A002A', line: '#F000FF',
    ink: '#FFFFFF', body: '#E2E8F0', muted: '#C79BFF',
    accent: '#00FFCC', accent2: '#F000FF',
    font: '"Courier New", Courier, monospace', light: false, glow: true, tags: ['dark', 'retro', 'fun'],
  },
  {
    slug: 'the-matrix', name: 'The Matrix',
    ground: '#000000', surface: '#000000', raised: '#002200', line: '#005500',
    ink: '#00FF41', body: '#00FF41', muted: '#008800',
    accent: '#00FF41', accent2: '#00FF41',
    font: '"Courier New", Courier, monospace', light: false, glow: true, tags: ['dark', 'fun'],
  },
  {
    slug: 'dracula', name: 'Dracula',
    ground: '#282A36', surface: '#282A36', raised: '#44475A', line: '#6272A4',
    ink: '#F8F8F2', body: '#F8F8F2', muted: '#9AA3CC',
    accent: '#BD93F9', accent2: '#FF79C6',
    font: SANS, light: false, glow: false, tags: ['dark', 'classic'],
  },
  {
    slug: 'amber-crt', name: 'Amber CRT',
    ground: '#0D0800', surface: '#0D0800', raised: '#1A1000', line: '#8B6300',
    ink: '#FFB000', body: '#FFB000', muted: '#CC8D00',
    accent: '#FFB000', accent2: '#FFB000',
    font: '"Courier New", Courier, monospace', light: false, glow: true, tags: ['dark', 'high-contrast', 'terminal'],
  },
  {
    slug: 'nordic-frost', name: 'Nordic Frost',
    ground: '#2E3440', surface: '#3B4252', raised: '#434C5E', line: '#4C566A',
    ink: '#ECEFF4', body: '#D8DEE9', muted: '#A8B3C4',
    accent: '#88C0D0', accent2: '#8FBCBB',
    font: SANS, light: false, glow: false, tags: ['dark', 'calm'],
  },
  {
    slug: 'solarized-deep', name: 'Solarized Deep',
    ground: '#002B36', surface: '#073642', raised: '#0B4653', line: '#175A67',
    ink: '#FDF6E3', body: '#D3CBB7', muted: '#93A1A1',
    accent: '#B58900', accent2: '#CB4B16',
    font: SANS, light: false, glow: false, tags: ['dark', 'classic'],
  },
  {
    slug: 'workshop-retro', name: 'Workshop Retro',
    ground: '#282828', surface: '#32302F', raised: '#3C3836', line: '#504945',
    ink: '#FBF1C7', body: '#EBDBB2', muted: '#BDAE93',
    accent: '#D79921', accent2: '#FE8019',
    font: MONO, light: false, glow: false, tags: ['dark', 'warm'],
  },
  {
    slug: 'high-contrast-dark', name: 'High Contrast Dark',
    ground: '#000000', surface: '#0A0A0A', raised: '#1A1A1A', line: '#E8E8E8',
    ink: '#FFFFFF', body: '#F2F2F2', muted: '#C9C9C9',
    accent: '#FFD400', accent2: '#FFE44D',
    font: SANS, light: false, glow: false, tags: ['dark', 'accessible', 'high-contrast'],
  },
  // ------------------------------------------------------------------ light
  {
    slug: 'daylight', name: 'Daylight',
    ground: '#FFFFFF', surface: '#F6F8FA', raised: '#EDF1F5', line: '#D6DEE7',
    ink: '#0B1727', body: '#33445A', muted: '#5C6E85',
    accent: '#0B62D6', accent2: '#0A56BC',
    font: SANS, light: true, glow: false, tags: ['light', 'everyday'],
  },
  {
    slug: 'forge-light', name: 'Forge Light',
    ground: '#FFFFFF', surface: '#F7F5F3', raised: '#F0EBE7', line: '#DED6CF',
    ink: '#1B1917', body: '#3D3833', muted: '#6B625A',
    accent: '#C2410C', accent2: '#EA580C',
    font: SANS, light: true, glow: false, tags: ['light', 'brand'],
  },
  {
    slug: 'paper-white', name: 'Paper White',
    ground: '#FBF9F4', surface: '#F4F0E8', raised: '#EAE4D9', line: '#D8D0C2',
    ink: '#231F1A', body: '#463F36', muted: '#6E655A',
    accent: '#8A5A2B', accent2: '#A66C33',
    font: SERIF, light: true, glow: false, tags: ['light', 'print-like'],
  },
  {
    slug: 'blueprint', name: 'Blueprint',
    ground: '#EEF3F8', surface: '#E1EAF3', raised: '#D3E0EE', line: '#B6C8DB',
    ink: '#0A2540', body: '#1F3E5E', muted: '#4C6C8C',
    accent: '#1B6AA5', accent2: '#EA580C',
    font: MONO, light: true, glow: false, tags: ['light', 'technical'],
  },
  {
    slug: 'clean-room', name: 'Clean Room',
    ground: '#F7FBFB', surface: '#ECF5F5', raised: '#DDEDEC', line: '#C3DBDA',
    ink: '#0C2422', body: '#254541', muted: '#4E6E6A',
    accent: '#0E8074', accent2: '#0B6B61',
    font: SANS, light: true, glow: false, tags: ['light', 'clinical'],
  },
  {
    slug: 'high-contrast-light', name: 'High Contrast Light',
    ground: '#FFFFFF', surface: '#FFFFFF', raised: '#EFEFEF', line: '#1A1A1A',
    ink: '#000000', body: '#111111', muted: '#3A3A3A',
    accent: '#0033CC', accent2: '#0022AA',
    font: SANS, light: true, glow: false, tags: ['light', 'accessible', 'high-contrast'],
  },
]

export const DEFAULT_THEME_SLUG = 'formlabs-forge'

export function paletteBySlug(slug: string | null | undefined): Palette {
  return PALETTES.find((p) => p.slug === slug) ?? PALETTES[0]
}

// preferred_theme is stored as the original app's own theme NAMES
// ("Formlabs Forge", "Vaporwave 1984", ...) - crud.update_user_theme takes
// any string and never validated against a fixed list, so an account that
// still carries one of the twenty-four names this pass didn't curate simply
// falls back to the default here rather than erroring.
export function paletteByName(name: string | null | undefined): Palette {
  return PALETTES.find((p) => p.name === name) ?? PALETTES[0]
}
