import api from './client'

export interface Case {
  id: number
  status: string
  assigned_inspector_id?: string | null
  inspector_name?: string
  district?: string
  building_id?: number
  description?: string
}

export interface CreateCasePayload {
  building_id: number
  description?: string
  inspector_id?: number
}

export async function listCases(params: Record<string, string | number> = {}): Promise<Case[]> {
  const { data } = await api.get<Case[]>(`/cases/`, { params })
  return data
}

export async function createCase(payload: { building_id?: number; anomaly_id?: number; notes?: string; created_by?: string }): Promise<{ id: number; status: string }> {
  const form = new FormData()
  if (payload.building_id != null) form.append('building_id', String(payload.building_id))
  if (payload.anomaly_id != null) form.append('anomaly_id', String(payload.anomaly_id))
  if (payload.notes) form.append('notes', payload.notes)
  if (payload.created_by) form.append('created_by', payload.created_by)
  const { data } = await api.post<{ id: number; status: string }>(`/cases/`, form)
  return data
}

export async function assignInspector(caseId: number, inspectorId: string, actor?: string): Promise<{ id: number; assigned_inspector_id: string }> {
  const form = new FormData()
  form.append('inspector_id', String(inspectorId))
  if (actor) form.append('actor', actor)
  const { data } = await api.post<{ id: number; assigned_inspector_id: string }>(`/cases/${caseId}/assign`, form)
  return data
}

export async function updateCaseStatus(caseId: number, newStatus: string, actor?: string): Promise<{ id: number; status: string }> {
  const form = new FormData()
  form.append('status', newStatus)
  if (actor) form.append('actor', actor)
  const { data } = await api.patch<{ id: number; status: string }>(`/cases/${caseId}/status`, form)
  return data
}

// Manager approval requires a report_id on backend; this is a simplified fallback
export async function decideCase(caseId: number, decision: string): Promise<{ id: number; status: string }> {
  // Fallback: mark as Closed; for full approval flow, call /cases/{id}/review with report_id
  return updateCaseStatus(caseId, 'Closed')
}

export async function getCaseDetail(caseId: number): Promise<any> {
  const { data } = await api.get(`/cases/${caseId}`)
  return data
}

export async function reviewCase(
  caseId: number,
  reportId: number,
  decision: 'Approve_Fraud' | 'Approve_NoIssue' | 'Recheck' | 'Reject',
  actor?: string,
) {
  const form = new FormData()
  form.append('report_id', String(reportId))
  form.append('decision', decision)
  if (actor) form.append('actor', actor)
  const { data } = await api.post(`/cases/${caseId}/review`, form)
  return data as {
    case_id: number
    case_status: string
    case_outcome: string | null
    report_id: number
    report_status: string
  }
}

export async function addCaseComment(caseId: number, note: string, actor?: string) {
  const form = new FormData()
  form.append('note', note)
  if (actor) form.append('actor', actor)
  const { data } = await api.post(`/cases/${caseId}/comment`, form)
  return data as { id: number; case_id: number }
}

export async function uploadCaseAttachment(caseId: number, file: File, uploaded_by?: string) {
  const form = new FormData()
  form.append('file', file)
  if (uploaded_by) form.append('uploaded_by', uploaded_by)
  const { data } = await api.post(`/cases/${caseId}/attachments`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data as { id: number; filename: string }
}

export async function addMeterReading(caseId: number, reading: number, unit = 'kWh', actor?: string) {
  const form = new FormData()
  form.append('reading', String(reading))
  form.append('unit', unit)
  if (actor) form.append('actor', actor)
  const { data } = await api.post(`/cases/${caseId}/reading`, form)
  return data as { id: number; case_id: number }
}

export interface InspectionReportPayload {
  inspector_id: string
  findings: string
  recommendation: string
}

export async function submitInspectionReport(caseId: number, payload: InspectionReportPayload) {
  const form = new FormData()
  form.append('inspector_id', payload.inspector_id)
  form.append('findings', payload.findings)
  form.append('recommendation', payload.recommendation)
  const { data } = await api.post(`/inspections/${caseId}/report`, form)
  return data as { message: string; report_id: number }
}
