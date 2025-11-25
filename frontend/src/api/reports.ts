import { api } from './client';

export type FraudTrendPoint = { period: string; fraud_rate: number; total: number; fraud: number };
export type DistrictAlert = { district: string; total_alerts: number; alert_rate: number };
export type ProductivityItem = { inspector: string; visits: number; closed: number };
export type BiasPoint = { district: string; bias_score: number; fraud: number; non_fraud: number };

export type AnalyticsResponse = {
  kpis: {
    total_cases: number;
    open_cases: number;
    closed_cases: number;
    avg_case_age_days: number;
    fraud_confirmation_rate: number;
    feedback_total: number;
    fraud_feedback: number;
    non_fraud_feedback: number;
  };
  fraud_trend: FraudTrendPoint[];
  district_alerts: DistrictAlert[];
  inspector_productivity: ProductivityItem[];
  bias_trend: BiasPoint[];
};

export const fetchAnalytics = async () => {
  const { data } = await api.get<AnalyticsResponse>('/reports/analytics');
  return data;
};

export type ReportExportKind = 'kpis' | 'cases' | 'appointments' | 'feedback';

export const exportReport = async (kind: ReportExportKind) => {
  const response = await api.get(`/reports/export`, {
    params: { kind, fmt: 'csv' },
    responseType: 'blob',
  });
  return response.data as Blob;
};
