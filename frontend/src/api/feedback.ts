// frontend/src/api/feedback.ts
type Label = 'fraud' | 'non_fraud' | 'uncertain';

export interface FeedbackLabelIn {
  case_id: number;
  label: Label;
  source?: string;   // e.g., 'manager_ui'
  notes?: string;
}

export interface FeedbackLabelOut {
  id: number;
  case_id: number;
  label: Label;
  source: string | null;
  notes: string | null;
  created_at: string;   // ISO
}

export interface FeedbackLogItem {
  id: number;
  case_id: number;
  meter_id: number | null;
  label: Label;
  source: string | null;
  notes: string | null;
  created_at: string;   // ISO
}

const API = (import.meta as any).env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';


function authHeaders() {
  const t = localStorage.getItem('token');
  return {
    'Content-Type': 'application/json',
    ...(t ? { Authorization: `Bearer ${t}` } : {}),
  };
}

export async function addFeedbackLabel(
  payload: FeedbackLabelIn
): Promise<FeedbackLabelOut> {
  const res = await fetch(`${API}/manager/feedback/labels`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listFeedbackLogs(params?: {
  from?: string; // 'YYYY-MM-DD'
  to?: string;   // 'YYYY-MM-DD'
}): Promise<FeedbackLogItem[]> {
  const q = new URLSearchParams();
  if (params?.from) q.append('from', params.from);
  if (params?.to) q.append('to', params.to);
  const res = await fetch(
    `${API}/manager/feedback/logs${q.toString() ? `?${q.toString()}` : ''}`,
    { headers: authHeaders() }
  );
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
