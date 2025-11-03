import api from './client'

export type UserRole = 'Citizen' | 'Inspector' | 'Manager' | 'Admin'

export interface UserRow {
  id: string
  email: string
  full_name?: string | null
  role: UserRole
  is_active: boolean
  created_at: string
}

export async function listUsers(): Promise<UserRow[]> {
  const res = await api.get<UserRow[]>('/users')
  return res.data
}

// Explicitly declare role as string (UserRole) to avoid type inference issues
export async function updateUserRole(userId: string, role: UserRole): Promise<UserRow> {
  const payload = { role: role as string }   // 👈 ensures it's a plain string in JSON
  const res = await api.patch<UserRow>(`/users/${userId}/role`, payload)
  return res.data
}