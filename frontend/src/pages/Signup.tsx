import React, { useMemo, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { signupCitizen } from '../api/auth'
import '../styles.css'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/i

type Strength = 'weak' | 'medium' | 'strong'
type Rules = { length: boolean; upper: boolean; lower: boolean; number: boolean; special: boolean }

const Signup: React.FC = () => {
  const nav = useNavigate()

  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const rules: Rules = useMemo(() => ({
    length: password.length >= 8,
    upper: /[A-Z]/.test(password),
    lower: /[a-z]/.test(password),
    number: /\d/.test(password),
    special: /[!@#$%^&*(),.?":{}|<>]/.test(password),
  }), [password])

  const strength: Strength = useMemo(() => {
    if (!password) return 'weak'
    const score = Object.values(rules).filter(Boolean).length
    if (score === 5) return 'strong'
    if (score >= 3) return 'medium'
    return 'weak'
  }, [rules, password])

  const meterWidth =
    password.length === 0 ? '0%' :
    strength === 'strong' ? '100%' :
    strength === 'medium' ? '66%' : '33%'

  const meterColor =
    strength === 'strong' ? '#53c76a' :
    strength === 'medium' ? '#FFC857' : '#E85C4A'

  const emailValid = useMemo(() => EMAIL_RE.test(email.trim()), [email])
  const mismatch = confirm.length > 0 && password !== confirm

  const canSubmit =
    !!fullName.trim() &&
    emailValid &&
    password.length > 0 &&
    !mismatch &&
    strength !== 'weak' &&
    !busy

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (!canSubmit) return
    try {
      setBusy(true)
      await signupCitizen(fullName.trim(), email.trim().toLowerCase(), password)
      nav('/login')
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Sign up failed. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      {/* 3) show navbar on the page */}

      <div className="auth-eco-bg">
        <div className="auth-wrapper">
          <form className="auth-card" onSubmit={handleSubmit}>

            

            <h2 className="auth-title">Create your account</h2>
            <p className="auth-sub">Join the Beirut Municipality Energy Transparency Portal</p>

            <div className="auth-field">
              <label className="auth-label">Full Name</label>
              <input
                className="auth-input"
                placeholder="Your full name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                autoComplete="name"
              />
            </div>

            <div className="auth-field">
              <label className="auth-label">Email</label>
              <input
                className="auth-input"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                type="email"
              />
            </div>

            {/* Password */}
            <div className="auth-field">
              <label className="auth-label">Password</label>
              <input
                className="auth-input"
                placeholder="Create a strong password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                type="password"
                autoComplete="new-password"
              />

              {/* Show strength bar + rules only once user starts typing */}
              {password.length > 0 && (
                <>
                  <div className="pw-meter" aria-hidden>
                    <div className="pw-bar" style={{ width: meterWidth, background: meterColor }} />
                  </div>

                  <div className="pw-reqs" role="list">
                    <span className={rules.length ? 'req-ok' : 'req-bad'}>
                      {rules.length ? '✔' : '✘'} At least 8 characters
                    </span>
                    <span className={rules.upper ? 'req-ok' : 'req-bad'}>
                      {rules.upper ? '✔' : '✘'} Uppercase letter
                    </span>
                    <span className={rules.lower ? 'req-ok' : 'req-bad'}>
                      {rules.lower ? '✔' : '✘'} Lowercase letter
                    </span>
                    <span className={rules.number ? 'req-ok' : 'req-bad'}>
                      {rules.number ? '✔' : '✘'} Number
                    </span>
                    <span className={rules.special ? 'req-ok' : 'req-bad'}>
                      {rules.special ? '✔' : '✘'} Special character
                    </span>
                  </div>
                </>
              )}
            </div>


            <div className="auth-field">
              <label className="auth-label">Confirm Password</label>
              <input
                className="auth-input"
                placeholder="Repeat password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                type="password"
                autoComplete="new-password"
              />
              {/* 4) mismatch helper text */}
              {mismatch && (
                <div className="helper-error">Passwords do not match.</div>
              )}
            </div>

            {error && (
              <div className="eco-card" style={{ marginTop: '.5rem', background: 'rgba(232,92,74,.12)', borderColor: 'rgba(232,92,74,.35)' }}>
                {error}
              </div>
            )}

            <div className="auth-actions" style={{ marginTop: '1rem' }}>
              <button className="btn-primary" disabled={!canSubmit}>
                {busy ? 'Creating…' : 'Create Account'}
              </button>
              <div className="auth-foot">
                <span>Already have an account? </span>
                <Link className="auth-link-strong" to="/login">Log in</Link>
              </div>
            </div>
          </form>
        </div>
      </div>
    </>
  )
}

export default Signup
