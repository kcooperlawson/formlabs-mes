import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { authApi } from '../api/auth'
import { ApiError } from '../api/client'
import { brandTitle } from '../brandTitle'
import { LaserSweep } from '../tv/PrintBuild'
import { useAuth } from './AuthProvider'

const inputCls = 'w-full rounded border border-[#334155] bg-[#0F172A] px-3 py-2.5 text-sm text-[#00D2FF] placeholder:text-[#475569] focus:border-[#00D2FF] focus:outline-none focus:ring-2 focus:ring-[#00D2FF]/20'
const labelCls = 'mb-1 block text-[0.68rem] font-extrabold uppercase tracking-wider text-[#94A3B8]'
const primaryBtn = 'w-full rounded bg-[#FF4B4B] py-3 text-sm font-extrabold uppercase tracking-wide text-white shadow transition hover:bg-[#ff6b6b] disabled:opacity-40'

type Tab = 'signin' | 'register'

function SignInForm() {
  const { login, loginError, isLoggingIn } = useAuth()
  const [username, setUsername] = useState('')
  const [pin, setPin] = useState('')
  const [remember, setRemember] = useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    login({ username, pin, remember })
  }

  return (
    <form onSubmit={handleSubmit}>
      <label className={labelCls}>Operator ID / Username</label>
      <input className={`${inputCls} mb-4`} placeholder="e.g. jsmith" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoFocus />

      <label className={labelCls}>Security PIN</label>
      <input className={`${inputCls} mb-4 tracking-widest`} type="password" inputMode="numeric" value={pin} onChange={(e) => setPin(e.target.value)} autoComplete="current-password" />

      <label className="mb-4 flex items-center gap-2 text-sm text-[#94A3B8]">
        <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
        💾 Remember this device
      </label>

      {loginError && (
        <p className="mb-4 rounded border border-red-800 bg-red-950 px-3 py-2 text-sm text-red-300">❌ {loginError}</p>
      )}

      <button type="submit" disabled={isLoggingIn} className={primaryBtn}>
        {isLoggingIn ? 'Signing in…' : 'Initialize Session'}
      </button>
    </form>
  )
}

const ROLES: Array<'Operator' | 'Packer'> = ['Operator', 'Packer']
const SHIFTS = ['Shift 1', 'Shift 2', 'Floater']

function RegisterForm() {
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [pin, setPin] = useState('')
  const [role, setRole] = useState<'Operator' | 'Packer'>('Operator')
  const [shift, setShift] = useState('Shift 1')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [pending, setPending] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setSuccess(false)
    if (!email.includes('@') || !email.includes('.')) {
      setError('Invalid email address format.')
      return
    }
    setPending(true)
    try {
      await authApi.register({ full_name: fullName, email, username, pin, role, shift })
      setSuccess(true)
      setFullName(''); setEmail(''); setUsername(''); setPin('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong.')
    } finally {
      setPending(false)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <label className={labelCls}>Full Name</label>
      <input className={`${inputCls} mb-3`} value={fullName} onChange={(e) => setFullName(e.target.value)} />

      <label className={labelCls}>Work Email</label>
      <input className={`${inputCls} mb-3`} placeholder="e.g. user@company.com" value={email} onChange={(e) => setEmail(e.target.value)} />

      <label className={labelCls}>Desired Operator ID</label>
      <input className={`${inputCls} mb-3`} value={username} onChange={(e) => setUsername(e.target.value)} />

      <label className={labelCls}>Create Security PIN</label>
      <input className={`${inputCls} mb-3`} type="password" value={pin} onChange={(e) => setPin(e.target.value)} />

      <div className="mb-4 grid grid-cols-2 gap-3">
        <div>
          <label className={labelCls}>Assigned Role</label>
          <select className={inputCls} value={role} onChange={(e) => setRole(e.target.value as 'Operator' | 'Packer')}>
            {ROLES.map((r) => <option key={r}>{r}</option>)}
          </select>
        </div>
        <div>
          <label className={labelCls}>Assigned Shift</label>
          <select className={inputCls} value={shift} onChange={(e) => setShift(e.target.value)}>
            {SHIFTS.map((s) => <option key={s}>{s}</option>)}
          </select>
        </div>
      </div>

      {error && <p className="mb-4 rounded border border-red-800 bg-red-950 px-3 py-2 text-sm text-red-300">⚠️ {error}</p>}
      {success && <p className="mb-4 rounded border border-emerald-800 bg-emerald-950 px-3 py-2 text-sm text-emerald-300">✅ Credentials logged! You may now sign in.</p>}

      <button type="submit" disabled={pending} className={primaryBtn}>
        {pending ? 'Registering…' : 'Register & Authenticate'}
      </button>
    </form>
  )
}

// Mirrors Home.py's login screen: a branded title that reads the plant's
// own mode setting before anyone has signed in, the printer graphic with
// its one-time laser sweep, and both the sign-in and self-registration
// tabs. This screen deliberately keeps the original's own cyan/monospace
// "security terminal" look rather than the Forge orange used everywhere
// after sign-in - that split exists in the original app too (see
// print_build.py / Home.py), not something this port introduced.
export function LoginPage() {
  const [tab, setTab] = useState<Tab>('signin')
  const modeQuery = useQuery({ queryKey: ['auth-mode'], queryFn: authApi.mode })
  const simpleMode = modeQuery.data?.simple_mode ?? true
  const { lead: titleLead, tail: titleTail, sub: titleSub } = brandTitle(simpleMode)

  return (
    <div className="flex min-h-svh items-center justify-center bg-[#0F172A] px-4 py-8">
      <div className="w-full max-w-md">
        <LaserSweep imageSrc="/form_printer.png" heightPx={132} />

        <div className="mb-6 text-center">
          <div className="mb-2 flex justify-center">
            <img src="/formlabs_logo.png" alt="" style={{ height: 56, filter: 'drop-shadow(0px 0px 10px rgba(0, 210, 255, 0.5))' }} />
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
            {titleLead} <span className="font-light text-[#00D2FF]">{titleTail}</span>
          </h1>
          <p className="mt-2 inline-block border-y border-[#1E293B] px-2 py-1.5 font-mono text-xs uppercase tracking-widest text-[#00D2FF]">
            {titleSub}
          </p>
        </div>

        <div className="rounded-lg border border-[#334155] bg-[#1E293B] p-6 shadow-[0_4px_10px_rgba(0,0,0,0.3)]">
          <div className="mb-5 flex gap-4 border-b border-[#334155]">
            <button
              onClick={() => setTab('signin')}
              className={`-mb-px border-b-2 pb-2 text-sm font-bold uppercase tracking-wide ${tab === 'signin' ? 'border-[#FF4B4B] text-white' : 'border-transparent text-[#94A3B8] hover:text-[#CBD5E1]'}`}
            >
              🔐 Secure Sign In
            </button>
            <button
              onClick={() => setTab('register')}
              className={`-mb-px border-b-2 pb-2 text-sm font-bold uppercase tracking-wide ${tab === 'register' ? 'border-[#FF4B4B] text-white' : 'border-transparent text-[#94A3B8] hover:text-[#CBD5E1]'}`}
            >
              📝 Register Access
            </button>
          </div>

          {tab === 'signin' ? <SignInForm /> : <RegisterForm />}
        </div>
      </div>
    </div>
  )
}
