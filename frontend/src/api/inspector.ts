import { api } from "./client"; // your Axios instance

export interface Appt {
  id: number;
  case_id: number;
  start: string;
  end: string;
  status: string;
  lat?: number;
  lng?: number;
}

export interface InspectorProfile {
  id: number;
  name: string;
  active: boolean;
  home_lat?: number | null;
  home_lng?: number | null;
  user_id?: string | null;
}

export const fetchInspectorProfile = () =>
  api.get<InspectorProfile>("/inspector/me").then((r) => r.data);

export const fetchSchedule = (day?: string, inspectorId?: number) =>
  api
    .get<Appt[]>("/inspector/schedule", { params: { inspector_id: inspectorId, day } })
    .then((r) => r.data);

export const respondAppt = (id: number, action: "accept" | "reject") =>
  api.patch<Appt>(`/inspector/appointments/${id}/respond`, { action }).then((r) => r.data);

export type ConfirmAction =
  | { action: "confirm" }
  | { action: "visited" }
  | { action: "reschedule"; start_time: string; end_time: string };

export const confirmVisit = (id: number, body: ConfirmAction) =>
  api.patch<Appt>(`/inspector/schedule/${id}/confirm`, body).then((r) => r.data);

export interface RoutePoint {
  id: number;
  lat: number;
  lng: number;
  case_id: number;
  start?: string;
}
export interface RouteOut {
  clusters: RoutePoint[][];
  ordered: RoutePoint[];
}

export const fetchRoutes = (day: string, inspectorId?: number) =>
  api
    .get<RouteOut>("/inspector/routes", { params: { inspector_id: inspectorId, day } })
    .then((r) => r.data);

export const downloadCasePdf = (caseId: number) =>
  api.get(`/inspector/reports/case/${caseId}.pdf`, { responseType: "blob" });

export const downloadWeeklyXlsx = (weekStart: string, inspectorId?: number) =>
  api.get(`/inspector/reports/weekly.xlsx`, {
    responseType: "blob",
    params: { inspector_id: inspectorId, week_start: weekStart },
  });

export type InspectorSummary = {
  inspector_id: number;
  pending: number;
  accepted: number;
  visited: number;
  closed_cases: number;
  fraud_detected: number;
  visits_today: number;
};

export const fetchInspectorSummary = () =>
  api.get<InspectorSummary>('/inspector/reports/inspector').then(r => r.data);
