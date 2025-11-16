import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { FaEye, FaEyeSlash } from 'react-icons/fa'
import { useAuth } from '../context/AuthContext'

const Login: React.FC = () => {
  const { signIn, loading } = useAuth()
  const nav = useNavigate()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showError, setShowError] = useState<string | null>(null)

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setShowError(null)
    try {
      await signIn(email.trim().toLowerCase(), password)
    } catch (err: any) {
      setShowError(err?.response?.data?.detail || 'Invalid email or password')
    }
  }

  return (
    <div className="auth-eco-bg">

      <div className="auth-wrapper">
        <form className="auth-card" onSubmit={onSubmit}>
          <h1 className="auth-title">Welcome back</h1>
          <p className="auth-sub">Log in to continue.</p>

          {showError && (
          <div className="eco-alert-error">
            {showError}
          </div>
        )}

          {/* Email */}
          <div className="auth-field">
            <label className="auth-label" htmlFor="email">Email</label>
            <input
              id="email"
              className="auth-input"
              placeholder="you@example.com"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          {/* Password with eye toggle */}
          <div className="auth-field" style={{ position: 'relative' }}>
            <label className="auth-label" htmlFor="password">Password</label>
            <input
              id="password"
              className="auth-input"
              placeholder="Your password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <button
              type="button"
              className="eye-btn"
              onClick={() => setShowPassword((prev) => !prev)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
            >
              {showPassword ? <FaEyeSlash /> : <FaEye />}
            </button>
          </div>

          <div className="auth-actions">
            <button className="btn-eco btn-wide" type="submit" disabled={loading}>
              {loading ? 'Logging in…' : 'Log In'}
            </button>
            <div className="auth-foot">
              Don’t have an account?{' '}
              <Link to="/signup" className="auth-link">Create one</Link>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}

export default Login
