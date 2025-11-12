import api from './client'

export type TicketRow = {
  id: number
  subject: string
  description: string
  status: string
  photo_path?: string | null
  created_at: string
  user_id?: number | null
}

export async function listTickets() {
  const { data } = await api.get<TicketRow[]>('/tickets')
  return data
}

