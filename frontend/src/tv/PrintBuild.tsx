// A shift, drawn as a print job - ported from print_build.py's pure HTML/CSS
// generators as React components instead of strings. Same colours, same
// timings (SLOW/ENTER/SWEEP/EASE below match the Python module exactly), same
// three rules: nothing loops, no travelling laser sweep across the part, and
// the product photo is positioned/revealed rather than redrawn.
const LASER = '#F97316'
const LASER_GLOW = 'rgba(249, 115, 22, 0.65)'
const EASE = 'cubic-bezier(0.22, 0.61, 0.36, 1)'
const SLOW = '900ms'
const ENTER = '500ms'
const LAYERS = 46

function clampPct(value: number): number {
  if (Number.isNaN(value)) return 0
  return Math.max(0, Math.min(100, value))
}

function layersDone(pct: number, layers = LAYERS): number {
  return Math.round((clampPct(pct) / 100) * Math.max(1, layers))
}

function buildCaption(pct: number, doneUnits?: number, targetUnits?: number, unit = 'L'): string {
  pct = clampPct(pct)
  const lead = pct >= 99.95 ? 'BUILD COMPLETE' : `LAYER ${String(Math.min(layersDone(pct), LAYERS - 1)).padStart(2, '0')} / ${LAYERS}`
  if (doneUnits != null && targetUnits) {
    return `${lead} · ${doneUnits.toLocaleString(undefined, { maximumFractionDigits: 0 })} / ${targetUnits.toLocaleString(undefined, { maximumFractionDigits: 0 })} ${unit}`
  }
  return lead
}

// A number whose digits roll to their new value instead of snapping - each
// digit is a 0-9 strip in a one-character window, moved by a CSS transition
// on `transform`. React keeps the same DOM node per digit position across
// renders (same key), so changing the translateY triggers the roll.
export function Odometer({ value, decimals = 0, uid = 'n' }: { value: number; decimals?: number; uid?: string }) {
  const number = Number.isFinite(value) ? value : 0
  const text = number.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
  return (
    <span style={{ display: 'inline-flex', alignItems: 'flex-end', lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>
      {text.split('').map((ch, i) => {
        if (/\d/.test(ch)) {
          const d = Number(ch)
          return (
            <span key={`${uid}-${i}`} style={{ display: 'inline-block', width: '0.62em', height: '1em', overflow: 'hidden', verticalAlign: 'bottom' }}>
              <span style={{ display: 'block', transform: `translateY(-${d}em)`, transition: `transform ${SLOW} ${EASE} ${(i * 0.04).toFixed(2)}s` }}>
                {Array.from({ length: 10 }, (_, n) => <span key={n} style={{ display: 'block', height: '1em' }}>{n}</span>)}
              </span>
            </span>
          )
        }
        return <span key={`${uid}-${i}`} style={{ display: 'inline-block', verticalAlign: 'bottom' }}>{ch}</span>
      })}
    </span>
  )
}

// The moment a shift's build finishes, played once - the caller (TvDashboardPage)
// decides when by only rendering this for a bounded window after 99.95%.
export function BuildFinale({ doneUnits, targetUnits, unit = 'L' }: { doneUnits?: number; targetUnits?: number; unit?: string }) {
  return (
    <div
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 26, flexWrap: 'wrap', textAlign: 'center',
        fontFamily: 'monospace', color: '#10B981', border: '2px solid #10B981', borderRadius: 10, padding: '14px 20px',
        margin: '6px 0 14px 0', background: 'rgba(16,185,129,0.12)', animation: `finale-enter ${ENTER} ease-out 1 forwards`,
      }}
    >
      <style>{'@keyframes finale-enter{0%{opacity:0;transform:scale(0.985);}100%{opacity:1;transform:scale(1);}}'}</style>
      <span style={{ fontSize: '2.1rem', fontWeight: 800, letterSpacing: '0.22em', whiteSpace: 'nowrap' }}>BUILD COMPLETE</span>
      {doneUnits != null && targetUnits ? (
        <span style={{ fontSize: '1.15rem', letterSpacing: '0.10em', opacity: 0.85, whiteSpace: 'nowrap' }}>
          {doneUnits.toLocaleString(undefined, { maximumFractionDigits: 0 })} / {targetUnits.toLocaleString(undefined, { maximumFractionDigits: 0 })} {unit} POURED
        </span>
      ) : null}
    </div>
  )
}

// The cartridge, built to `pct` of the shift's expected output - a ghost of
// the whole part so the target shape reads from the first layer, the real
// image clipped to the height built so far, and a laser line riding the
// current layer until the build finishes.
export function CartridgeBuild({
  pct, imageSrc, doneUnits, targetUnits, unit = 'L', heightPx = 300, finale = false,
}: {
  pct: number; imageSrc: string; doneUnits?: number; targetUnits?: number; unit?: string; heightPx?: number; finale?: boolean
}) {
  pct = clampPct(pct)
  const done = pct >= 99.95
  const clip = `inset(${(100 - pct).toFixed(2)}% 0 0 0)`

  return (
    <div style={{ position: 'relative', width: '100%', height: heightPx, display: 'flex', alignItems: 'flex-end', justifyContent: 'center' }}>
      {done && finale && (
        <style>{'@keyframes cartridge-lift{0%{transform:translateY(0);filter:drop-shadow(0 2px 3px rgba(0,0,0,0.35));}100%{transform:translateY(-10px);filter:drop-shadow(0 16px 22px rgba(0,0,0,0.55));}}'}</style>
      )}
      <div
        style={{
          position: 'relative', height: '100%', aspectRatio: '0.42', maxWidth: '100%',
          animation: done && finale ? 'cartridge-lift 1.1s ' + EASE + ' 1.4s 1 forwards' : undefined,
        }}
      >
        {!done && (
          <img
            src={imageSrc} alt=""
            style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'contain', opacity: 0.3, filter: 'grayscale(1) brightness(2.9) contrast(0.45)', zIndex: 1 }}
          />
        )}
        <img
          src={imageSrc} alt="Cartridge fill progress"
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'contain', zIndex: 2, clipPath: clip, transition: `clip-path ${SLOW} ${EASE}` }}
        />
        <div
          style={{
            position: 'absolute', inset: 0, zIndex: 3, clipPath: clip, transition: `clip-path ${SLOW} ${EASE}`,
            background: `repeating-linear-gradient(to top, rgba(0,0,0,0.22) 0px, rgba(0,0,0,0.22) 1px, transparent 1px, transparent ${Math.max(3, Math.floor(heightPx / LAYERS))}px)`,
            mixBlendMode: 'multiply', pointerEvents: 'none',
          }}
        />
        {!done && pct > 0.4 && (
          <div
            style={{
              position: 'absolute', left: '-6%', right: '-6%', bottom: `calc(${pct.toFixed(2)}% - 1px)`, height: 2,
              background: LASER, boxShadow: `0 0 10px 2px ${LASER_GLOW}`, transition: `bottom ${SLOW} ${EASE}`, zIndex: 4,
            }}
          />
        )}
      </div>
      <div
        style={{
          position: 'absolute', bottom: -32, left: 0, right: 0, textAlign: 'center', fontFamily: 'monospace',
          letterSpacing: '0.10em', fontSize: '0.74rem', lineHeight: 1.5, whiteSpace: 'nowrap', color: done ? '#10B981' : LASER,
        }}
      >
        {buildCaption(pct, doneUnits, targetUnits, unit)}
      </div>
    </div>
  )
}

// A progress bar laid down in layers rather than poured as one block.
export function LayerBar({ pct, heightPx = 14, color = '#00D2FF', layers = 34 }: { pct: number; heightPx?: number; color?: string; layers?: number }) {
  pct = clampPct(pct)
  const slicePx = Math.max(2, Math.round(240 / Math.max(1, layers)))
  return (
    <div style={{ width: '100%', height: heightPx, borderRadius: 3, background: '#0B1220', border: '1px solid #1E2B45', overflow: 'hidden', position: 'relative' }}>
      <div
        style={{
          width: `${pct.toFixed(2)}%`, height: '100%', transition: `width ${SLOW} ${EASE}`,
          background: `repeating-linear-gradient(to right, ${color} 0px, ${color} ${slicePx - 1}px, rgba(0,0,0,0.45) ${slicePx - 1}px, rgba(0,0,0,0.45) ${slicePx}px)`,
        }}
      />
    </div>
  )
}

// One laser pass down the whole screen, as it arrives - the caller renders
// this once, on mount, and never again for the life of the tab.
export function ScreenSweep() {
  return (
    <>
      <style>{'@keyframes screen-sweep{0%{top:-4vh;opacity:0;}8%{opacity:0.95;}92%{opacity:0.95;}100%{top:104vh;opacity:0;}}'}</style>
      <div
        style={{
          position: 'fixed', left: 0, right: 0, height: 2, top: '-4vh', opacity: 0, zIndex: 998, pointerEvents: 'none',
          background: LASER, boxShadow: `0 0 22px 5px ${LASER_GLOW}`, animation: 'screen-sweep 1.8s ease-in-out 0.3s 1 forwards',
        }}
      />
    </>
  )
}

// The machine, with a laser passing over it once as the screen arrives -
// ported from print_build.py's laser_sweep(), used by the login screen.
// Streamlit's version plays this on the first two renders specifically to
// dodge a double-glitch its own cookie-restore rerun caused; React never
// re-mounts this component on a keystroke the way Streamlit reran the whole
// script, so there's nothing to dodge here - it plays once, on mount, which
// is what the original was working around Streamlit's own execution model
// to approximate in the first place.
export function LaserSweep({ imageSrc, heightPx = 210 }: { imageSrc: string; heightPx?: number }) {
  return (
    <div style={{ position: 'relative', height: heightPx, display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
      <style>{'@keyframes laser-sweep-vert{0%{top:-6%;opacity:0;}10%{opacity:1;}90%{opacity:1;}100%{top:104%;opacity:0;}}'}</style>
      <img
        src={imageSrc} alt=""
        style={{ height: '100%', objectFit: 'contain', filter: 'drop-shadow(0 14px 26px rgba(0,0,0,0.65))' }}
      />
      <div
        style={{
          position: 'absolute', left: '8%', right: '8%', height: 2, top: '-6%', opacity: 0,
          background: LASER, boxShadow: `0 0 14px 3px ${LASER_GLOW}`, animation: 'laser-sweep-vert 2.4s ease-in-out 1 forwards',
        }}
      />
    </div>
  )
}
