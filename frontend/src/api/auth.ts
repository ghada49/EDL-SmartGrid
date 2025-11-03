import api from './client'
interface User {
  id: string
  email: string
  role: string
  is_active: boolean
  full_name: string 
}
export async function login(email: string, password: string) {
  const res = await api.post('/auth/login', { email, password })
  return res.data as { access_token: string; token_type: string }
}

export async function signupCitizen(full_name: string, email: string, password: string) {
  const res = await api.post('/auth/signup', { full_name, email, password })
  return res.data
}


export async function me() {
  const res = await api.get('/users/me')
  return res.data as { id: string; email: string; role: string; is_active: boolean , full_name: string }
}

