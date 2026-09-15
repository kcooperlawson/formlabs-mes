import { type ReactNode, useEffect, useRef } from 'react'
import { useAuth } from './auth/AuthProvider'
import { DEFAULT_THEME_SLUG, paletteByName } from './palettes'
import { buildThemeStylesheet } from './themeCss'

const STYLE_TAG_ID = 'fl-theme-palettes'
const TRANSITION_MS = 500

// Injects the generated palette stylesheet once, then keeps <html
// data-theme="..."> in sync with the signed-in user's own preferred_theme -
// the one place that watches account state and applies it, the same job
// ui_shell.py's THEMES[active_theme] lookup did on every Streamlit rerun.
// Logged-out screens (the login page) always see the bare :root default
// (Formlabs Forge) because there's no user yet to read a preference from.
export function ThemeRoot({ children }: { children: ReactNode }) {
  const { user } = useAuth()

  useEffect(() => {
    if (document.getElementById(STYLE_TAG_ID)) return
    const style = document.createElement('style')
    style.id = STYLE_TAG_ID
    style.textContent = buildThemeStylesheet()
    document.head.appendChild(style)
  }, [])

  const slug = user ? paletteByName(user.preferred_theme).slug : DEFAULT_THEME_SLUG
  const isFirstApply = useRef(true)

  useEffect(() => {
    const root = document.documentElement
    // A brief, app-wide colour/border crossfade on the moment of switching -
    // not on every render, and not on first paint (which would fade in from
    // whatever the browser's own default background is).
    if (!isFirstApply.current) {
      root.classList.add('fl-theme-transition')
      window.setTimeout(() => root.classList.remove('fl-theme-transition'), TRANSITION_MS)
    }
    isFirstApply.current = false
    if (slug === DEFAULT_THEME_SLUG) {
      root.removeAttribute('data-theme')
    } else {
      root.dataset.theme = slug
    }
  }, [slug])

  return <>{children}</>
}
