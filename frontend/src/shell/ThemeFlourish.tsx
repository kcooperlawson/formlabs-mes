import { type ReactNode, useEffect, useRef } from 'react'

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
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
    const GLYPHS = 'アイウエオカキクケコサシスセソ01'
    let cols: number[] = []

    function resize() {
      const parent = canvas!.parentElement
      canvas!.width = parent?.clientWidth ?? window.innerWidth
      canvas!.height = parent?.clientHeight ?? window.innerHeight
      cols = new Array(Math.ceil(canvas!.width / FONT_SIZE)).fill(0).map(() => Math.random() * -40)
    }
    resize()
    window.addEventListener('resize', resize)

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
      window.removeEventListener('resize', resize)
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
function GridHorizon({ color }: { color: string }) {
  return (
    <div className="absolute inset-x-0 bottom-0 h-2/3 overflow-hidden" style={{ perspective: '200px' }}>
      <div
        className="absolute inset-0"
        style={{
          backgroundImage:
            `linear-gradient(${color}66 1px, transparent 1px), linear-gradient(90deg, ${color}66 1px, transparent 1px)`,
          backgroundSize: '48px 48px',
          transform: 'rotateX(78deg)',
          transformOrigin: 'bottom',
          animation: 'fl-grid-scroll 2.6s linear infinite',
        }}
      />
    </div>
  )
}

// One optional, deliberately subtle background flourish per "retro" theme -
// opt-in personality for the themes that asked for it (see palettes.ts's
// `glow` flag and the conversation that led to Vaporwave 1984/Synthwave
// Sunrise/The Matrix/Amber CRT being curated in), never for the working
// Formlabs Forge default or anything meant to look plainly professional.
// Absolutely positioned behind the caller's own content (z-0, pointer-events
// none) - the caller just needs `position: relative` on its own root.
export function ThemeFlourish({ slug }: { slug: string }) {
  if (prefersReducedMotion()) return null

  let inner: ReactNode = null
  if (slug === 'the-matrix') inner = <MatrixRain color="#00FF41" />
  else if (slug === 'amber-crt') inner = <ScanlineOverlay />
  else if (slug === 'vaporwave-1984') inner = <GridHorizon color="#FF007F" />
  else if (slug === 'synthwave-sunrise') inner = <GridHorizon color="#FF416C" />
  else return null

  return <div className="pointer-events-none absolute inset-0 z-0 overflow-hidden">{inner}</div>
}
