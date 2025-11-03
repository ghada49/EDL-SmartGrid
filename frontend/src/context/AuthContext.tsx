import React, { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { login as apiLogin, me as apiMe, signupCitizen as apiSignupCitizen } from '../api/auth'
import { useNavigate } from 'react-router-dom'

type Role = 'Citizen' | 'Inspector' | 'Manager' | 'Admin' | null

interface AuthState {
  token: string | null
  role: Role
  full_name: string | null
  loading: boolean
  signIn: (email: string, password: string) => Promise<void>
  signOut: () => void
  signUpCitizen: (full_name: string, email: string, password: string) => Promise<void>
}

const AuthContext = createContext<AuthState | undefined>(undefined)

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'))
  const [role, setRole] = useState<Role>((localStorage.getItem('role') as Role) || null)
  const [loading, setLoading] = useState<boolean>(false)
  const [full_name, setFullName] = useState<string | null>(localStorage.getItem('full_name'))
  const navigate = useNavigate()

  const redirectByRole = (r: Role) => {
    if (r === 'Citizen') navigate('/citizen')
    else if (r === 'Inspector') navigate('/inspector')
    else if (r === 'Manager' || r === 'Admin') navigate('/manager')
  }

  useEffect(() => {
    const hydrate = async () => {
      if (!token) return
      try {
        const u = await apiMe()
        setRole(u.role as Role)
        setFullName(u.full_name)
        localStorage.setItem('role', u.role)
        localStorage.setItem('full_name', u.full_name)
      } catch {
        localStorage.removeItem('token')
        localStorage.removeItem('role')
        localStorage.removeItem('full_name')
        setToken(null)
        setRole(null)
        setFullName(null)
      }
    }
    hydrate()
  }, [token])


  const signIn = async (email: string, password: string) => {
    setLoading(true)
    try {
      const { access_token } = await apiLogin(email, password)
      localStorage.setItem('token', access_token)
      setToken(access_token)
      const u = await apiMe()
      setRole(u.role as Role)
      setFullName(u.full_name)
      localStorage.setItem('role', u.role)
      localStorage.setItem('full_name', u.full_name)
      redirectByRole(u.role as Role)
    } finally {
      setLoading(false)
    }
  }


  const signUpCitizen = async (full_name: string, email: string, password: string) => {
  setLoading(true)
  try {
    await apiSignupCitizen(full_name, email, password)
    navigate('/login')
  } finally {
    setLoading(false)
  }
}


  const signOut = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('role')
    setToken(null)
    setRole(null)
    navigate('/login')
  }
  const value = useMemo<AuthState>(
  () => ({ token, role, full_name, loading, signIn, signOut, signUpCitizen }),
  [token, role, full_name, loading]
)

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

