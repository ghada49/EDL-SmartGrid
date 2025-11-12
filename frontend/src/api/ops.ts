import api from './client'

export type DQ = {
  row_count: number
  missingness: Record<string, number>
}

export type UploadDatasetResponse = {
  status: string
  rows_ingested: number
  saved_as: string
  dq?: DQ
  columns?: DriftRecord[]
}

export type DriftRecord = {
  column: string
  ref_mean: number
  new_mean: number
  z_score: number
  drift_flag: boolean
  method?: string
}

export async function uploadDataset(file: File) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<UploadDatasetResponse>('/ops/upload_dataset', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function getDriftReport(file: File) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<{ columns: DriftRecord[] }>('/ops/drift_report', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function analyzeDataset(file: File) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<{ dq: DQ; columns: DriftRecord[] }>('/ops/analyze', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export type DatasetHistoryRow = {
  id: number
  filename: string
  rows: number
  uploaded_at: string
  status: string
}

export async function getDatasetHistory() {
  const { data } = await api.get<DatasetHistoryRow[]>('/ops/datasets/history')
  return data
}
