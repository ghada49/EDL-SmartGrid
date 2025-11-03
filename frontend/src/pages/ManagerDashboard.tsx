import React, { useEffect, useState } from 'react'
import TopNav from '../components/TopNav'
import { listUsers, updateUserRole, UserRow } from '../api/users'
import { useAuth } from '../context/AuthContext'
import { FaUsersCog, FaDatabase, FaBalanceScale, FaSlidersH, FaShieldAlt } from 'react-icons/fa'

const ManagerDashboard: React.FC = () => {
  const { role: myRole } = useAuth()
  const [users, setUsers] = useState<UserRow[]>([])
  const [busy, setBusy] = useState<string | null>(null)

  const load = async () => {
    try { setUsers(await listUsers()) } catch { /* TODO: toast */ }
  }
  useEffect(() => { load() }, [])

  const canTouchInspectorCycle = (u: UserRow) =>
    (myRole === 'Manager' || myRole === 'Admin') &&
    (u.role === 'Citizen' || u.role === 'Inspector')

  const canAdminMakeManager = (u: UserRow) =>
    myRole === 'Admin' && u.role === 'Citizen'

  const promoteToInspector = async (u: UserRow) => {
    if (busy) return
    setBusy(u.id)
    try { await updateUserRole(u.id, 'Inspector'); await load() }
    finally { setBusy(null) }
  }

  const demoteToCitizen = async (u: UserRow) => {
    if (busy) return
    setBusy(u.id)
    try { await updateUserRole(u.id, 'Citizen'); await load() }
    finally { setBusy(null) }
  }

  const promoteToManager = async (u: UserRow) => {
    if (busy) return
    setBusy(u.id)
    try { await updateUserRole(u.id, 'Manager'); await load() }
    finally { setBusy(null) }
  }

  return (
    <div className="ms-home">
      {/* Fixed navbar at the very top */}
      <TopNav />

      {/* Offset content so it doesn't hide behind the fixed nav */}
      <div className="page-shell">
        <div className="eco-page">
          <header className="eco-hero">
            <h1 className="eco-title">Admin / Manager Console</h1>
            <p className="eco-sub">Manage users, datasets, models, thresholds and audit logs.</p>
          </header>

          {/* KPI strip */}
          <section className="eco-kpi-strip">
            <div className="eco-kpi glassy">
              <div className="eco-kpi-num">1,237</div>
              <div className="eco-kpi-label">Total Tickets</div>
            </div>
            <div className="eco-kpi glassy">
              <div className="eco-kpi-num">412</div>
              <div className="eco-kpi-label">Flagged Buildings</div>
            </div>
            <div className="eco-kpi glassy">
              <div className="eco-kpi-num">6.4d</div>
              <div className="eco-kpi-label">Avg. Resolution Time</div>
            </div>
          </section>

          <section className="eco-grid two">
            {/* ---- User Management ---- */}
            <div className="eco-card">


              <div className="eco-table compact">
                <div className="eco-thead">
                  <span>Name</span>
                  <span>Email</span>
                  <span>Role</span>
                  <span>Actions</span>
                </div>

                {users.map(u => (
                  <div className="eco-row" key={u.id}>
                    <span>{u.full_name || '—'}</span>
                    <span>{u.email}</span>
                    <span>{u.role}</span>
                    <span className="eco-actions">
                      {canTouchInspectorCycle(u) && u.role === 'Citizen' && (
                        <button className="btn-eco sm" disabled={busy===u.id} onClick={() => promoteToInspector(u)}>
                          Promote to Inspector
                        </button>
                      )}
                      {canTouchInspectorCycle(u) && u.role === 'Inspector' && (
                        <button className="btn-outline sm" disabled={busy===u.id} onClick={() => demoteToCitizen(u)}>
                          Demote to Citizen
                        </button>
                      )}
                      {canAdminMakeManager(u) && (
                        <button className="btn-eco sm" disabled={busy===u.id} onClick={() => promoteToManager(u)}>
                          Promote to Manager
                        </button>
                      )}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Dataset Upload */}
            <div className="eco-card">
              <div className="eco-card-head">
                <h3><FaDatabase className="eco-icon-sm" /> Dataset Upload</h3>
              </div>
              <p className="eco-muted">Upload CSV (schema checked). Versioning & drift report.</p>
              <div className="eco-actions">
                <button className="btn-eco">Upload CSV</button>
                <button className="btn-outline">Run Drift Report</button>
              </div>
            </div>

            {/* Thresholds */}
            <div className="eco-card">
              <div className="eco-card-head">
                <h3><FaSlidersH className="eco-icon-sm" /> Thresholds</h3>
              </div>
              <p className="eco-muted">Adjust alert sensitivity for IF/AE & combined rank.</p>
              <div className="eco-slider">
                <label>Isolation Forest Threshold <span>0.78</span></label>
                <input type="range" min="0" max="1" step="0.01" defaultValue="0.78" />
              </div>
              <div className="eco-slider">
                <label>Autoencoder Threshold <span>0.74</span></label>
                <input type="range" min="0" max="1" step="0.01" defaultValue="0.74" />
              </div>
              <div className="eco-actions">
                <button className="btn-eco">Save Thresholds</button>
              </div>
            </div>

            {/* Audit */}
            <div className="eco-card">
              <div className="eco-card-head">
                <h3><FaBalanceScale className="eco-icon-sm" /> Bias & Audit</h3>
              </div>
              <ul className="eco-steps">
                <li>2025-02-24 — Model v1.2 activated</li>
                <li>2025-02-10 — IF threshold changed (0.75 → 0.78)</li>
                <li>2025-01-23 — Case #921 status: Visited → Closed</li>
              </ul>
              <div className="eco-actions">
                <button className="btn-outline"><FaShieldAlt /> View Full Audit</button>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}

export default ManagerDashboard