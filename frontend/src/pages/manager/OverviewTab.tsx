// src/pages/manager/OverviewTab.tsx
import { useEffect, useState } from "react";
import { listInspectors, workload, Inspector, WorkloadItem } from "../../api/scheduling";
import { fetchAnalytics, AnalyticsResponse } from "../../api/reports";
import { listCases, Case } from "../../api/cases";
import { listTickets, TicketRow } from "../../api/tickets";

export default function OverviewTab() {
  const [ins, setIns] = useState<Inspector[]>([]);
  const [wl, setWl] = useState<WorkloadItem[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cases, setCases] = useState<Case[]>([]);
  const [tickets, setTickets] = useState<TicketRow[]>([]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [inspectors, wlData, analyticsData, caseData, ticketData] = await Promise.all([
          listInspectors(true),
          workload(),
          fetchAnalytics(),
          listCases(),
          listTickets(),
        ]);
        setIns(inspectors);
        setWl(wlData);
        setAnalytics(analyticsData);
        setCases(caseData);
        setTickets(ticketData);
      } catch (err: any) {
        setError(err?.response?.data?.detail || err?.message || "Failed to load overview data");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const formatPercent = (value: number) =>
    `${(value * 100).toFixed(value * 100 >= 1 ? 1 : 2)}%`;

  const formatNumber = (value: number) =>
    new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(value);

  const formatCoords = (lat?: number | null, lng?: number | null) => {
    if (lat == null || lng == null) return "—";
    return `📍 ${lat.toFixed(4)}, ${lng.toFixed(4)}`;
  };

  const totalCases = cases.length;
  const openCases = cases.filter((c) => (c.status || "").toLowerCase() !== "closed").length;
  const closedCases = cases.filter((c) => (c.status || "").toLowerCase() === "closed").length;
  const totalTickets = tickets.length;
  const openTickets = tickets.filter((t) => t.status !== "Closed").length;
  const closedTickets = tickets.filter((t) => t.status === "Closed").length;

  return (
    <>
      <div className="eco-grid two">
        <div className="eco-card eco-card--tight">
          <div className="eco-card-head">
            <h3>Overview KPIs</h3>
          </div>
          {error && <div className="eco-alert warn" style={{ marginBottom: 8 }}>{error}</div>}
          <div className="eco-kpi-strip">
            <div className="eco-kpi glassy">
              <div className="eco-kpi-num">{formatNumber(totalCases)}</div>
              <div className="eco-kpi-label">Total cases</div>
            </div>
            <div className="eco-kpi glassy">
              <div className="eco-kpi-num">{formatNumber(openCases)}</div>
              <div className="eco-kpi-label">Open</div>
            </div>
            <div className="eco-kpi glassy">
              <div className="eco-kpi-num">{formatNumber(closedCases)}</div>
              <div className="eco-kpi-label">Closed</div>
            </div>
            <div className="eco-kpi glassy">
              <div className="eco-kpi-num">{formatNumber(totalTickets)}</div>
              <div className="eco-kpi-label">Total tickets</div>
            </div>
            <div className="eco-kpi glassy">
              <div className="eco-kpi-num">{formatNumber(openTickets)}</div>
              <div className="eco-kpi-label">Open tickets</div>
            </div>
            <div className="eco-kpi glassy">
              <div className="eco-kpi-num">{formatNumber(closedTickets)}</div>
              <div className="eco-kpi-label">Closed tickets</div>
            </div>
          </div>
          {loading && <p className="eco-muted">Loading overview…</p>}
        </div>

        <div className="eco-card">
          <div className="eco-card-head">
            <h3>Fraud Trend</h3>
          </div>
          {analytics?.fraud_trend && analytics.fraud_trend.length > 0 ? (
            <ol className="eco-steps">
              {analytics.fraud_trend.map((point) => (
                <li key={point.period}>
                  {point.period}: {formatPercent(point.fraud_rate)} ({point.total} labels)
                </li>
              ))}
            </ol>
          ) : (
            <p className="eco-muted">No feedback data captured yet.</p>
          )}
        </div>
      </div>

      <div className="eco-grid two" style={{ marginTop: "12px" }}>
        <div className="eco-card">
          <div className="eco-card-head">
            <h3>Inspectors</h3>
          </div>
          <div className="eco-table compact">
            <div className="eco-thead">
              <span>ID</span>
              <span>Name</span>
              <span>Home Location</span>
            </div>
            {ins.map((i) => (
              <div key={i.id} className="eco-row">
                <span>{i.id}</span>
                <span>{i.name}</span>
                <span>{formatCoords(i.home_lat, i.home_lng)}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="eco-card">
          <div className="eco-card-head">
            <h3>Workload (this week)</h3>
          </div>
          <div className="eco-table compact">
            <div className="eco-thead">
              <span>Inspector</span>
              <span>Active cases</span>
              <span>Appts this week</span>
            </div>
            {wl.map((w) => (
              <div key={w.inspector_id} className="eco-row">
                <span>{w.inspector_name}</span>
                <span>{w.active_cases}</span>
                <span>{w.appointments_this_week}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
