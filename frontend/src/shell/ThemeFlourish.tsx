import { type ReactNode, useEffect, useRef, useState } from 'react'

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

const FLOURISH_KEY = 'mes_flourish_disabled'
// localStorage alone has no listener for "I just changed this from
// somewhere else in the same tab" - the storage event only fires in OTHER
// tabs. AccountPanel's toggle and ThemeFlourish itself are two unrelated
// components with no shared state otherwise, so a plain window event is
// what makes flipping the checkbox actually disappear the animation on the
// spot rather than only on the next full reload.
const FLOURISH_EVENT = 'mes-flourish-pref-changed'

// A second, manual switch alongside prefers-reduced-motion - that one is an
// OS/browser-level accessibility setting nobody should have to fight with
// just to get a plain background, and this is a plain preference for
// somebody who finds the crawl distracting but has no vestibular reason to
// have reduced-motion set system-wide. Saved to this device only, same
// reasoning as sound/chimes.ts's isMuted: a shared floor terminal's own
// preference isn't necessarily whoever happens to be signed into it right
// now, and there's nothing to sync to an account here either.
export function flourishesDisabled(): boolean {
  try {
    return localStorage.getItem(FLOURISH_KEY) === '1'
  } catch {
    return false
  }
}

export function setFlourishesDisabled(disabled: boolean) {
  try {
    localStorage.setItem(FLOURISH_KEY, disabled ? '1' : '0')
  } catch {
    /* a private window or blocked storage just means the choice isn't remembered */
  }
  window.dispatchEvent(new Event(FLOURISH_EVENT))
}

// A slow, low-opacity digital rain behind the working area - not a full-fps
// canvas loop (a plant floor terminal is not the machine to spend a
// requestAnimationFrame budget on for decoration), just a plain interval
// redrawing a few columns at a time. Never rendered at all under
// prefers-reduced-motion.
function MatrixRain({ color }: { color: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return

    const FONT_SIZE = 18
    // Plain binary, not the movie's katakana - this app's own rain, not a
    // recreation of it.
    const GLYPHS = '01'
    let cols: number[] = []

    function resize() {
      const parent = canvas!.parentElement
      canvas!.width = parent?.clientWidth ?? window.innerWidth
      canvas!.height = parent?.clientHeight ?? window.innerHeight
      cols = new Array(Math.ceil(canvas!.width / FONT_SIZE)).fill(0).map(() => Math.random() * -40)
    }
    resize()
    // A window resize listener alone misses the far more common case on the
    // Operator Form: the PAGE growing taller as fields appear (station picked,
    // a changeover banner, lot verification...), which changes this canvas's
    // own parent height without the window itself ever resizing. A
    // ResizeObserver on the parent catches that too, so the rain still
    // covers a card that grew well past the height it had on mount.
    const ro = new ResizeObserver(resize)
    if (canvas.parentElement) ro.observe(canvas.parentElement)

    const id = window.setInterval(() => {
      ctx.fillStyle = 'rgba(0, 0, 0, 0.06)'
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      ctx.fillStyle = color
      ctx.font = `${FONT_SIZE}px monospace`
      cols.forEach((y, i) => {
        ctx.fillText(GLYPHS[Math.floor(Math.random() * GLYPHS.length)], i * FONT_SIZE, y)
        cols[i] = y > canvas.height && Math.random() > 0.975 ? 0 : y + FONT_SIZE
      })
    }, 80)

    return () => {
      window.clearInterval(id)
      ro.disconnect()
    }
  }, [color])

  return <canvas ref={canvasRef} className="h-full w-full" style={{ opacity: 0.16 }} />
}

function ScanlineOverlay() {
  return (
    <div
      className="h-full w-full"
      style={{
        backgroundImage:
          'repeating-linear-gradient(to bottom, rgba(255,255,255,0.05) 0px, rgba(255,255,255,0.05) 1px, transparent 1px, transparent 3px)',
        animation: 'fl-scanline-flicker 6s ease-in-out infinite',
      }}
    />
  )
}

// The classic synthwave/vaporwave receding grid, in one accent colour - a
// perspective-tilted repeating grid whose background-position slides toward
// the viewer on a loop.
//
// A 200px perspective with a 78deg tilt (the first version of this) folds
// the grid down so hard that 1px lines cross several screen pixels at once
// near the horizon - the browser's own anti-aliasing then breaks each of
// those into short dashes instead of a solid line, which is most visible on
// Vaporwave 1984's fully-saturated magenta and easy to miss on Synthwave
// Sunrise's softer coral-pink even though the same thing is happening
// there too. A gentler tilt with much more room to recede in fixes it at
// the source rather than fighting the artifact with a thicker line; 2px
// lines (up from 1) still help on the segments closest to the "camera"
// where the foreshortening is lightest.
function GridHorizon({ color }: { color: string }) {
  return (
    <div className="absolute inset-x-0 bottom-0 h-2/3 overflow-hidden" style={{ perspective: '700px' }}>
      <div
        className="absolute inset-0"
        style={{
          backgroundImage:
            `linear-gradient(${color}66 2px, transparent 2px), linear-gradient(90deg, ${color}66 2px, transparent 2px)`,
          backgroundSize: '48px 48px',
          transform: 'rotateX(65deg)',
          transformOrigin: 'bottom',
          animation: 'fl-grid-scroll 4s linear infinite',
        }}
      />
    </div>
  )
}

// Three thin scan-lines drifting down the screen, each its own colour,
// speed and start delay, flickering in and out rather than staying at a
// flat opacity the whole way down - a glitching hologram/HUD read rather
// than the clean geometric grid the two synthwave themes already get.
// Plain `top` animation, not `transform: translateY`, deliberately: a bar
// has to travel exactly the height of whatever contains it regardless of
// that container's own size, and top's percentages already are relative to
// that; a transform distance would have to be hard-coded in pixels or
// guessed in viewport units that don't actually match this container.
function GlitchScan({ colorA, colorB }: { colorA: string; colorB: string }) {
  const bars = [
    { color: colorA, duration: '5s', delay: '0s', height: 2 },
    { color: colorB, duration: '6.5s', delay: '2.1s', height: 1 },
    { color: colorA, duration: '7.5s', delay: '4.3s', height: 1 },
  ]
  return (
    <div className="relative h-full w-full">
      {bars.map((b, i) => (
        <div
          key={i}
          className="absolute inset-x-0"
          style={{
            height: b.height,
            background: b.color,
            boxShadow: `0 0 8px ${b.color}`,
            animation: `fl-glitch-scan ${b.duration} ${b.delay} linear infinite`,
          }}
        />
      ))}
    </div>
  )
}

// One optional, deliberately subtle background flourish per "retro" theme -
// opt-in personality for the themes that asked for it (see palettes.ts's
// `glow` flag and the conversation that led to Vaporwave 1984/Synthwave
// Sunrise/The Matrix/Amber CRT/Neon Cyberpunk being curated in), never for
// the working Formlabs Forge default or anything meant to look plainly
// professional. Absolutely positioned behind the caller's own content (z-0,
// pointer-events none) - the caller just needs `position: relative` on its
// own root.
const FLOURISH_SLUGS = new Set(['the-matrix', 'amber-crt', 'vaporwave-1984', 'synthwave-sunrise', 'neon-cyberpunk'])

// Whether ThemeFlourish would actually render anything for this slug right
// now - shared with any container (OperatorFormPage's card) that wants to
// react to the same reduced-motion/disabled switches, e.g. to lighten its
// own background so the effect has something to show through instead of
// going translucent over a plain solid colour for a theme with no flourish.
export function useFlourishVisible(slug: string): boolean {
  const [disabled, setDisabled] = useState(flourishesDisabled)
  useEffect(() => {
    const onChange = () => setDisabled(flourishesDisabled())
    window.addEventListener(FLOURISH_EVENT, onChange)
    return () => window.removeEventListener(FLOURISH_EVENT, onChange)
  }, [])
  return !disabled && !prefersReducedMotion() && FLOURISH_SLUGS.has(slug)
}

export function ThemeFlourish({ slug }: { slug: string }) {
  const visible = useFlourishVisible(slug)
  if (!visible) return null

  let inner: ReactNode = null
  if (slug === 'the-matrix') inner = <MatrixRain color="#00FF41" />
  else if (slug === 'amber-crt') inner = <ScanlineOverlay />
  else if (slug === 'vaporwave-1984') inner = <GridHorizon color="#FF007F" />
  else if (slug === 'synthwave-sunrise') inner = <GridHorizon color="#FF416C" />
  else if (slug === 'neon-cyberpunk') inner = <GlitchScan colorA="#00FFCC" colorB="#F000FF" />
  else return null

  return <div className="pointer-events-none absolute inset-0 z-0 overflow-hidden">{inner}</div>
}
