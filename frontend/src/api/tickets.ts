// api/tickets.ts
import api from "./client";

// Matches backend/models/ops.py Ticket
export type TicketRow = {
  id: number;
  user_id: string;
  user_email?: string | null;
  subject: string;
  description: string;
  status: string;
  photo_path?: string | null;
  created_at: string;
};

// GET /tickets (manager)
export const listTickets = (params?: any): Promise<TicketRow[]> =>
  api.get("/tickets", { params }).then((r) => r.data);

// GET /tickets/{id}
export const getTicket = (id: number): Promise<TicketRow> =>
  api.get(`/tickets/${id}`).then((r) => r.data);

// PATCH /tickets/{id}/status
export const updateTicketStatus = (id: number, status: string) => {
  const form = new FormData();
  form.append("status", status);
  return api.patch(`/tickets/${id}/status`, form);
};

// POST /tickets/{id}/followup
export const addTicketFollowup = (id: number, note: string) => {
  const form = new FormData();
  form.append("note", note);
  return api.post(`/tickets/${id}/followup`, form);
};
