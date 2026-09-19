// Short, synthesized tones - no audio files to bundle, no network fetch,
// and every terminal hears the exact same sound regardless of device.
// Two cues, each doing one job: a log just landed (playLogged), and the
// lot check just caught a real mismatch (playAlert) - the system doing
// exactly what it's for, worth a sound distinct from an ordinary log,
// not a siren, since this is a catch, not an emergency.
//
// Muted per-device, not per-account: whether a terminal makes noise is a
// property of where it physically sits (next to someone's ear vs. across
// a loud floor), not of who happens to be signed into it right now.

const MUTE_KEY = 'mes_sound_muted'

export function isMuted(): boolean {
  try {
    return localStorage.getItem(MUTE_KEY) === '1'
  } catch {
    return false
  }
}

export function setMuted(muted: boolean) {
  try {
    localStorage.setItem(MUTE_KEY, muted ? '1' : '0')
  } catch {
    /* a private window or blocked storage just means the choice isn't remembered */
  }
}

let ctx: AudioContext | null = null

// Safari in particular refuses to start audio at all unless a context was
// created or resumed from directly inside a real user gesture - by the
// time a network round trip (a mutation's onSuccess) comes back, that
// gesture has ended. primeAudio() is called from the very first
// pointerdown/keydown anywhere in the app (see main.tsx) specifically so
// the context is already running well before either cue is ever due to
// play - every real interaction happens after that first tap.
export function primeAudio() {
  if (typeof window === 'undefined') return
  const AudioCtor = window.AudioContext ?? (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
  if (!AudioCtor) return
  if (!ctx) ctx = new AudioCtor()
  if (ctx.state === 'suspended') void ctx.resume()
}

function tone(freq: number, at: number, dur: number, peak = 0.15) {
  if (!ctx) return
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.type = 'sine'
  osc.frequency.value = freq
  const start = ctx.currentTime + at
  // A fast linear rise then an exponential decay - a hard on/off click
  // reads as a glitch rather than a note; this is what makes a plain
  // sine wave sound like an actual chime instead of a beep test.
  gain.gain.setValueAtTime(0, start)
  gain.gain.linearRampToValueAtTime(peak, start + 0.015)
  gain.gain.exponentialRampToValueAtTime(0.0001, start + dur)
  osc.connect(gain)
  gain.connect(ctx.destination)
  osc.start(start)
  osc.stop(start + dur + 0.05)
}

function play(notes: Array<{ freq: number; at: number; dur: number }>) {
  if (isMuted()) return
  primeAudio()
  if (!ctx) return
  for (const n of notes) tone(n.freq, n.at, n.dur)
}

// Deliberately not gated by isMuted(): muting sound is about not making
// noise other people on the floor hear, and a vibration is private to
// whoever is holding the phone - the two are different disturbances with
// different owners. Two browsers can never produce this, on any platform,
// through no fault of this code: iOS Safari (and every other iOS browser -
// they all sit on WebKit) never shipped the Vibration API at all, same
// story as the install-prompt gap elsewhere in this app; Firefox quietly
// disabled real vibration on Android in 2020 over abuse concerns, then
// removed navigator.vibrate entirely, desktop included, in Firefox 129
// (August 2024). Both are a silent no-op here, not a broken feature -
// Chrome, Samsung Internet and Edge on Android are the ones that actually
// buzz.
function vibrate(pattern: number | number[]) {
  try {
    navigator.vibrate?.(pattern)
  } catch {
    /* some browsers throw rather than returning false off a real gesture */
  }
}

// C6 then E6, ~200ms total - bright and short enough to not stack up if
// several logs land close together.
export function playLogged() {
  play([
    { freq: 1046.5, at: 0, dur: 0.11 },
    { freq: 1318.5, at: 0.09, dur: 0.16 },
  ])
  vibrate(30)
}

// A lower two-note pair, descending rather than rising, so the ear tells
// it apart from playLogged without anyone looking at the screen first. The
// vibration follows the same shape: one buzz for an ordinary log, two short
// ones here, so the catch is felt as different too, not just heard.
export function playAlert() {
  play([
    { freq: 415.3, at: 0, dur: 0.14 },
    { freq: 311.1, at: 0.11, dur: 0.22 },
  ])
  vibrate([40, 60, 40])
}
