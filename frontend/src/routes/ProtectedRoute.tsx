import React from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

type Props = {
  roles: string[]
  children: React.ReactNode
}

const ProtectedRoute: React.FC<Props> = ({ roles, children }) => {
  const { token, role } = useAuth()
  if (!token) return <Navigate to="/login" replace />
  if (!role || !roles.includes(role)) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default ProtectedRoute

