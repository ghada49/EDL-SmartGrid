// src/api/scheduling.ts
import { api } from './client'; // your axios instance

export interface Inspector {
  id: number; name: string; active: boolean;
  home_lat?: number | null; home_lng?: number | null;
  email?: string | null;
  user_id?: string | null;
}
export interface Appointment {
  id: number;
  case_id: number;
  inspector_id: number | null;
  start_time: string; // ISO
  end_time: string;   // ISO
  status: 'pending'|'accepted'|'closed'|string;
  title?: string | null;
  lat?: number | null; lng?: number | null;
}
export interface WorkloadItem {
  inspector_id: number; inspector_name: string;
  active_cases: number; appointments_this_week: number;
}
export interface SuggestReq {
  case_id?: number;
  lat?: number; lng?: number;
  strategy?: 'proximity'|'load';
  top_k?: number;
}
export interface Suggestion {
  inspector_id: number; inspector_name: string; score: number; reason: string;
}
export type OverviewInspector = {
  inspector_id: number;
  inspector_name: string;
  capacity?: number | null;
  active_cases: number;
  appointments: Appointment[];
}

export type OverviewOut = {
  day: string; // YYYY-MM-DD
  inspectors: OverviewInspector[];
}

export type AssignmentResult = {
  case_id: number;
  inspector_id: number;
  reason: string; // "distance_km" | "balanced_load"
  score: number;
}

export async function listInspectors(active_only=true): Promise<Inspector[]> {
  const {data} = await api.get('/manager/scheduling/inspectors', { params: { active_only }});
  return data;
}
export async function listAppointments(params: {
  start?: string; end?: string; inspector_id?: number;
}): Promise<Appointment[]> {
  const {data} = await api.get('/manager/scheduling/appointments', { params });
  return data;
}
export async function workload(): Promise<WorkloadItem[]> {
  const {data} = await api.get('/manager/scheduling/workload'); return data;
}
export async function suggest(req: SuggestReq): Promise<Suggestion[]> {
  const {data} = await api.post('/manager/scheduling/suggest', req); return data;
}
export async function assignVisit(body: {
  case_id: number;
  inspector_id: number;
  start_time: string;
  end_time: string;
  notes?: string;
  target_lat?: number;
  target_lng?: number;
}): Promise<Appointment> {
  const {data} = await api.post('/manager/scheduling/assign', body); return data;
}
export async function reschedule(apptId: number, body: { start_time: string; end_time: string; inspector_id?: number }): Promise<Appointment> {
  const {data} = await api.patch(`/manager/scheduling/appointments/${apptId}/reschedule`, body); return data;
}
export async function reassign(apptId: number, body: { inspector_id: number }): Promise<Appointment> {
  const {data} = await api.patch(`/manager/scheduling/appointments/${apptId}/reassign`, body); return data;
}
export async function overview(day?: string): Promise<OverviewOut> {
  const { data } = await api.get('/manager/scheduling/schedule/overview', { params: day ? { day } : {} });
  return data;
}

export async function autoAssign(body: {
  case_ids: number[];
  strategy: 'proximity' | 'balanced';   // <-- align with backend /schedule/auto-assign
  start_time?: string;                   // ISO
  duration_minutes?: number;
  max_radius_km?: number;
}): Promise<AssignmentResult[]> {
  const { data } = await api.post('/manager/scheduling/schedule/auto-assign', body);
  return data;
}
