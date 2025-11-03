import React from 'react'
import { Link } from 'react-router-dom'
import { FaMapMarkedAlt, FaRoute, FaClipboardCheck, FaDownload } from 'react-icons/fa'

const InspectorRoutes: React.FC = () => {
  return (
    <div className="eco-page">
      <header className="eco-hero">
        <h1 className="eco-title">Inspector Console</h1>
        <p className="eco-sub">Prioritize visits, view flagged buildings and manage your cases.</p>
      </header>

      <section className="eco-grid">
        {/* Flagged buildings */}
        <div className="eco-card">
          <div className="eco-card-head">
            <h3>Flagged Buildings</h3>
            <span className="eco-chip">Live</span>
          </div>
          <p className="eco-muted">Buildings flagged by anomaly models (IF/AE). Filter by district or score.</p>

          <div className="eco-table">
            <div className="eco-thead">
              <span>Building</span><span>IF</span><span>AE</span><span>Rank</span><span>Actions</span>
            </div>
            {/* Example rows (replace with API data) */}
            {[
              { id: 342, if: 0.86, ae: 0.78, rank: 0.82 },
              { id: 118, if: 0.91, ae: 0.74, rank: 0.85 },
              { id: 507, if: 0.77, ae: 0.81, rank: 0.79 },
            ].map(r => (
              <div className="eco-row" key={r.id}>
                <span>#B{r.id}</span>
                <span>{r.if.toFixed(2)}</span>
                <span>{r.ae.toFixed(2)}</span>
                <span><b>{r.rank.toFixed(2)}</b></span>
                <span className="eco-actions">
                  <Link to={`/buildings/${r.id}`} className="btn-eco sm">Profile</Link>
                  <Link to={`/cases/new?building=${r.id}`} className="btn-outline sm">Create Case</Link>
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Route / Schedule */}
        <div className="eco-card">
          <div className="eco-card-head">
            <h3>Today’s Route</h3>
            <FaRoute className="eco-icon-sm" />
          </div>
          <p className="eco-muted">Optimized by proximity & combined anomaly rank.</p>

          <ol className="eco-steps">
            <li>08:30 — #B342 (Mar Elias)</li>
            <li>10:15 — #B118 (Ain El Mreisse)</li>
            <li>12:00 — #B507 (Tariq El Jdide)</li>
          </ol>

          <div className="eco-actions">
            <button className="btn-eco"><FaDownload /> Download Route CSV</button>
            <Link to="/inspections/new" className="btn-outline">Assign Extra Stop</Link>
          </div>

          <div className="eco-map">
            <FaMapMarkedAlt size={28} />
            <span>Map placeholder — show markers + polyline route</span>
          </div>
        </div>

        {/* Case quick actions */}
        <div className="eco-card">
          <div className="eco-card-head">
            <h3>My Cases</h3>
            <FaClipboardCheck className="eco-icon-sm" />
          </div>
          <p className="eco-muted">Move cases across the workflow. Keep notes & photos.</p>

          <div className="eco-kpis">
            <div className="eco-kpi">
              <div className="eco-kpi-num">8</div>
              <div className="eco-kpi-label">New</div>
            </div>
            <div className="eco-kpi">
              <div className="eco-kpi-num">5</div>
              <div className="eco-kpi-label">Scheduled</div>
            </div>
            <div className="eco-kpi">
              <div className="eco-kpi-num">3</div>
              <div className="eco-kpi-label">Visited</div>
            </div>
          </div>

          <div className="eco-actions">
            <Link to="/cases" className="btn-eco">Open Case Board</Link>
          </div>
        </div>
      </section>
    </div>
  )
}

export default InspectorRoutes
