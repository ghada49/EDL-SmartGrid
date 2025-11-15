import { useEffect, useState } from 'react';
import {
  AnalyticsResponse,
  exportReport,
  fetchAnalytics,
  ReportExportKind,
} from '../../api/reports';

const formatPercent = (value: number) =>
  `${(value * 100).toFixed(value * 100 >= 1 ? 1 : 2)}%`;

const formatNumber = (value: number) =>
  new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 }).format(value);

export default function ReportingTab() {
  const [data, setData] = useState<AnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<ReportExportKind | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchAnalytics());
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to load analytics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const triggerExport = async (kind: ReportExportKind) => {
    try {
      setDownloading(kind);
      const blob = await exportReport(kind);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${kind}_report.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      alert(err?.response?.data?.detail || err?.message || 'Export failed');
    } finally {
      setDownloading(null);
    }
  };

  if (loading) {
    return <div className="eco-card">Loading analytics…</div>;
  }
  if (error) {
    return (
      <div className="eco-card">
        <div className="eco-error" style={{ marginBottom: 12 }}>{error}</div>
        <button className="btn-outline" onClick={load}>Retry</button>
      </div>
    );
  }
  if (!data) return null;

  return (
    <div className="eco-grid two">
      <div className="eco-card">
        <div className="eco-card-head">
          <h3>Key KPIs</h3>
          <div className="eco-actions">
            <button
              className="btn-eco sm"
              onClick={() => triggerExport('kpis')}
              disabled={downloading === 'kpis'}
            >
              {downloading === 'kpis' ? 'Preparing…' : 'Download CSV'}
            </button>
          </div>
        </div>
        <div className="eco-kpi-strip">
          <div className="eco-kpi glassy">
            <div className="eco-kpi-num">{formatNumber(data.kpis.total_cases)}</div>
            <div className="eco-kpi-label">Total cases</div>
          </div>
          <div className="eco-kpi glassy">
            <div className="eco-kpi-num">{formatNumber(data.kpis.open_cases)}</div>
            <div className="eco-kpi-label">Open</div>
          </div>
          <div className="eco-kpi glassy">
            <div className="eco-kpi-num">{formatNumber(data.kpis.closed_cases)}</div>
            <div className="eco-kpi-label">Closed</div>
          </div>
          <div className="eco-kpi glassy">
            <div className="eco-kpi-num">{formatPercent(data.kpis.fraud_confirmation_rate)}</div>
            <div className="eco-kpi-label">Fraud confirmation</div>
          </div>
        </div>
        <p className="eco-muted">
          Average case age: {formatNumber(data.kpis.avg_case_age_days)} days · Feedback records:{' '}
          {data.kpis.feedback_total}
        </p>
      </div>

      <div className="eco-card">
        <div className="eco-card-head">
          <h3>District Alerts</h3>
        </div>
        {data.district_alerts.length === 0 ? (
          <p className="eco-muted">No district level alerts yet.</p>
        ) : (
          <div className="eco-table compact">
            <div className="eco-thead">
              <span>District</span>
              <span>Alerts</span>
              <span>Rate</span>
            </div>
            {data.district_alerts.map(item => (
              <div className="eco-row" key={item.district}>
                <span>{item.district}</span>
                <span>{item.total_alerts}</span>
                <span style={{ width: '100%' }}>
                  <div className="analytics-bar">
                    <div
                      className="analytics-bar-fill"
                      style={{ width: `${Math.min(100, item.alert_rate * 100)}%` }}
                    />
                  </div>
                  <small>{formatPercent(item.alert_rate)}</small>
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="eco-card">
        <div className="eco-card-head">
          <h3>Inspector Productivity</h3>
          <button
            className="btn-outline sm"
            onClick={() => triggerExport('appointments')}
            disabled={downloading === 'appointments'}
          >
            {downloading === 'appointments' ? 'Preparing…' : 'Export appointments'}
          </button>
        </div>
        {data.inspector_productivity.length === 0 ? (
          <p className="eco-muted">No inspector activity recorded.</p>
        ) : (
          <div className="eco-table compact">
            <div className="eco-thead">
              <span>Inspector</span>
              <span>Visits</span>
              <span>Closed</span>
            </div>
            {data.inspector_productivity.map(item => (
              <div className="eco-row" key={item.inspector}>
                <span>{item.inspector}</span>
                <span>{item.visits}</span>
                <span>{item.closed}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="eco-card">
        <div className="eco-card-head">
          <h3>Fraud Trend</h3>
          <button className="btn-outline sm" onClick={load}>
            Refresh
          </button>
        </div>
        {data.fraud_trend.length === 0 ? (
          <p className="eco-muted">No feedback data captured yet.</p>
        ) : (
          <ol className="eco-steps">
            {data.fraud_trend.map(point => (
              <li key={point.period}>
                {point.period}: {formatPercent(point.fraud_rate)} ({point.total} labels)
              </li>
            ))}
          </ol>
        )}
      </div>

      <div className="eco-card">
        <div className="eco-card-head">
          <h3>Bias Trend</h3>
          <button
            className="btn-outline sm"
            onClick={() => triggerExport('feedback')}
            disabled={downloading === 'feedback'}
          >
            {downloading === 'feedback' ? 'Preparing…' : 'Export feedback'}
          </button>
        </div>
        {data.bias_trend.length === 0 ? (
          <p className="eco-muted">Not enough feedback to analyse bias.</p>
        ) : (
          <div className="eco-table compact">
            <div className="eco-thead">
              <span>District</span>
              <span>Bias score</span>
              <span>Fraud / Non</span>
            </div>
            {data.bias_trend.map(point => (
              <div className="eco-row" key={point.district}>
                <span>{point.district}</span>
                <span>{formatPercent(point.bias_score)}</span>
                <span>
                  {point.fraud} / {point.non_fraud}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="eco-card">
        <div className="eco-card-head">
          <h3>Case Inventory</h3>
          <button
            className="btn-outline sm"
            onClick={() => triggerExport('cases')}
            disabled={downloading === 'cases'}
          >
            {downloading === 'cases' ? 'Preparing…' : 'Download cases CSV'}
          </button>
        </div>
        <p className="eco-muted">
          Use the exports above to build weekly/monthly PDF/XLSX reports or share raw CSV with the
          admin team.
        </p>
      </div>
    </div>
  );
}
