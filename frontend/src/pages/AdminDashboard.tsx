import React, { useEffect, useState } from "react";
import { listUsers, updateUserRole, UserRow } from "../api/users";
import { useAuth } from "../context/AuthContext";
import {
  FaDatabase,
  FaBalanceScale,
  FaSlidersH,
  FaShieldAlt,
} from "react-icons/fa";

import { Tabs } from "../components/Tabs";
import { uploadDataset, getDatasetHistory, DQ } from "../api/ops";

// --- Local helper types for dataset drift & history ---
type DriftRow = {
  column: string;
  z_score: number;
  drift_flag: boolean;
  method?: string;
};

type DatasetHistoryRow = {
  id: number;
  filename: string;
  rows: number;
  uploaded_at: string;
  status: string;
};

const AdminDashboard: React.FC = () => {
  const { role: myRole } = useAuth();

  // ───── User Management ─────
  const [users, setUsers] = useState<UserRow[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  const loadUsers = async () => {
    try {
      const data = await listUsers();
      setUsers(data);
    } catch (err) {
      console.error("Failed to load users:", err);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const canTouchInspectorCycle = (u: UserRow) =>
    (myRole === "Manager" || myRole === "Admin") &&
    (u.role === "Citizen" || u.role === "Inspector");

  const canAdminMakeManager = (u: UserRow) =>
    myRole === "Admin" && u.role === "Citizen";

  const promoteToInspector = async (u: UserRow) => {
    if (busy) return;
    setBusy(u.id);
    try {
      await updateUserRole(u.id, "Inspector");
      await loadUsers();
    } finally {
      setBusy(null);
    }
  };

  const demoteToCitizen = async (u: UserRow) => {
    if (busy) return;
    setBusy(u.id);
    try {
      await updateUserRole(u.id, "Citizen");
      await loadUsers();
    } finally {
      setBusy(null);
    }
  };

  const promoteToManager = async (u: UserRow) => {
    if (busy) return;
    setBusy(u.id);
    try {
      await updateUserRole(u.id, "Manager");
      await loadUsers();
    } finally {
      setBusy(null);
    }
  };

  // ───── Dataset Upload / Drift / History ─────
  const [uploadDQ, setUploadDQ] = useState<DQ | null>(null);
  const [drift, setDrift] = useState<DriftRow[]>([]);
  const [history, setHistory] = useState<DatasetHistoryRow[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  // ───── Tabs (for design only) ─────
  const [tab, setTab] = useState<"Overview" | "Users" | "Data & Models" | "Audit">(
    "Overview"
  );

  if (!myRole) {
    return <div>Loading...</div>;
  }

  return (
    <div className="ms-home">

      <div className="page-shell">
        <div className="eco-page">
          {/* ── Hero header (same style as Manager) ── */}
          <header className="eco-hero">
            <h1 className="eco-title">Admin Console</h1>
            <p className="eco-sub">
              Govern users, datasets, thresholds, and audit trail for the fraud detection system.
            </p>
          </header>

          {/* ── Tabs strip (design, light behavior) ── */}
          <Tabs
            tabs={["Overview", "Users", "Data & Models", "Audit"]}
            active={tab}
            onChange={(t) => setTab(t as any)}
          />

          {/* ── KPI strip (purely visual) ── */}
          <section className="eco-kpi-strip">
            <div className="eco-kpi glassy">
              <div className="eco-kpi-num">{users.length}</div>
              <div className="eco-kpi-label">Registered Users</div>
            </div>
            <div className="eco-kpi glassy">
              <div className="eco-kpi-num">
                {users.filter((u) => u.role === "Inspector").length}
              </div>
              <div className="eco-kpi-label">Active Inspectors</div>
            </div>
            <div className="eco-kpi glassy">
              <div className="eco-kpi-num">
                {history.length > 0 ? history.length : "—"}
              </div>
              <div className="eco-kpi-label">Dataset Versions</div>
            </div>
          </section>

          {/* ── Main grid, similar to Manager ── */}
          <section className="eco-grid two">
            {/* LEFT COLUMN: depends on tab */}
            <div className="eco-card">
              {tab === "Overview" && (
                <>
                  <div className="eco-card-head">
                    <h3>System Overview</h3>
                  </div>
                  <p className="eco-muted">
                    High-level view of platform usage and data governance. Use the tabs above to
                    jump to users, datasets, or audit trail.
                  </p>
                </>
              )}

              {tab === "Users" && (
                <>
                  <div className="eco-card-head">
                    <h3>
                      <FaShieldAlt className="eco-icon-sm" /> User Management
                    </h3>
                  </div>

                  <div className="eco-table compact">
                    <div className="eco-thead">
                      <span>Name</span>
                      <span>Email</span>
                      <span>Role</span>
                      <span>Actions</span>
                    </div>

                    {users.map((u) => (
                      <div className="eco-row" key={u.id}>
                        <span>{u.full_name || "—"}</span>
                        <span>{u.email}</span>
                        <span>{u.role}</span>
                        <span className="eco-actions">
                          {canTouchInspectorCycle(u) && u.role === "Citizen" && (
                            <button
                              className="btn-eco sm"
                              disabled={busy === u.id}
                              onClick={() => promoteToInspector(u)}
                            >
                              Promote to Inspector
                            </button>
                          )}
                          {canTouchInspectorCycle(u) && u.role === "Inspector" && (
                            <button
                              className="btn-outline sm"
                              disabled={busy === u.id}
                              onClick={() => demoteToCitizen(u)}
                            >
                              Demote to Citizen
                            </button>
                          )}
                          {canAdminMakeManager(u) && (
                            <button
                              className="btn-eco sm"
                              disabled={busy === u.id}
                              onClick={() => promoteToManager(u)}
                            >
                              Promote to Manager
                            </button>
                          )}
                        </span>
                      </div>
                    ))}
                  </div>
                </>
              )}

              {tab === "Data & Models" && (
                <>
                  <div className="eco-card-head">
                    <h3>
                      <FaDatabase className="eco-icon-sm" /> Dataset Upload
                    </h3>
                  </div>
                  <p className="eco-muted">
                    Upload CSV/XLSX (schema checked). The system keeps a versioned history and
                    runs data quality checks and drift detection.
                  </p>

                  <div
                    className="eco-actions"
                    style={{ display: "flex", gap: 12, alignItems: "center" }}
                  >
                    <label className="btn-eco">
                      Upload CSV/XLSX
                      <input
                        type="file"
                        accept=".csv,.xlsx"
                        style={{ display: "none" }}
                        onChange={async (e) => {
                          const f = e.target.files?.[0];
                          if (!f) return;
                          try {
                            const res = await uploadDataset(f);
                            setUploadDQ(res.dq || null);

                            if ((res as any).columns) {
                              setDrift(
                                (res as any).columns.map((c: any) => ({
                                  column: c.column,
                                  z_score: c.z_score,
                                  drift_flag: c.drift_flag,
                                  method: c.method,
                                }))
                              );
                            } else {
                              setDrift([]);
                            }

                            setShowHistory(false);

                            try {
                              const hist = await getDatasetHistory();
                              setHistory(hist);
                            } catch {
                              // history optional
                            }

                            try {
                              alert(
                                `Upload successful: ${res.rows_ingested} rows ingested`
                              );
                            } catch {
                              /* ignore alert error */
                            }
                          } catch (err: any) {
                            alert(
                              `Upload failed: ${
                                err?.response?.data?.detail || err.message
                              }`
                            );
                          } finally {
                            e.currentTarget.value = "";
                          }
                        }}
                      />
                    </label>

                    <button
                      className="btn-outline"
                      onClick={async () => {
                        if (showHistory) {
                          setShowHistory(false);
                          return;
                        }
                        try {
                          const hist = await getDatasetHistory();
                          setHistory(hist);
                          setShowHistory(true);
                        } catch (err: any) {
                          alert(
                            `History failed: ${
                              err?.response?.data?.detail || err.message
                            }`
                          );
                        }
                      }}
                    >
                      {showHistory ? "Hide History" : "View History"}
                    </button>
                  </div>

                  {/* Data Quality */}
                  {uploadDQ && (
                    <div className="eco-table compact" style={{ marginTop: 12 }}>
                      <div className="eco-thead">
                        <span>Column</span>
                        <span>Missingness</span>
                      </div>
                      {Object.entries(uploadDQ.missingness).map(([c, m]) => (
                        <div className="eco-row" key={c}>
                          <span>{c}</span>
                          <span>{((m as number) * 100).toFixed(1)}%</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Drift report */}
                  {drift.length > 0 && (
                    <div className="eco-table compact" style={{ marginTop: 12 }}>
                      <div className="eco-thead">
                        <span>Column</span>
                        <span>Score</span>
                        <span>Drift</span>
                      </div>
                      {drift.map((d) => (
                        <div className="eco-row" key={d.column}>
                          <span>
                            {d.column}
                            {d.method ? ` (${d.method.toUpperCase()})` : ""}
                          </span>
                          <span>{d.z_score.toFixed(4)}</span>
                          <span>{d.drift_flag ? "Yes" : "No"}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* History */}
                  {showHistory && history.length > 0 && (
                    <div className="eco-table compact" style={{ marginTop: 12 }}>
                      <div className="eco-thead">
                        <span>ID</span>
                        <span>Filename</span>
                        <span>Rows</span>
                        <span>Uploaded</span>
                        <span>Status</span>
                      </div>
                      {history.map((h) => (
                        <div className="eco-row" key={h.id}>
                          <span>{h.id}</span>
                          <span>{h.filename}</span>
                          <span>{h.rows}</span>
                          <span>{new Date(h.uploaded_at).toLocaleString()}</span>
                          <span>{h.status}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}

              {tab === "Audit" && (
                <>
                  <div className="eco-card-head">
                    <h3>
                      <FaBalanceScale className="eco-icon-sm" /> Bias &amp; Audit
                    </h3>
                  </div>
                  <p className="eco-muted">
                    Snapshot of recent governance actions. This is a visual placeholder; you can
                    later hook it to your real audit log API.
                  </p>
                  <ul className="eco-steps">
                    <li>2025-02-24 — Model v1.2 activated</li>
                    <li>2025-02-10 — IF threshold changed (0.75 → 0.78)</li>
                    <li>2025-01-23 — Case #921 status: Visited → Closed</li>
                  </ul>
                  <div className="eco-actions">
                    <button className="btn-outline">
                      <FaShieldAlt /> View Full Audit
                    </button>
                  </div>
                </>
              )}
            </div>

            {/* RIGHT COLUMN: Thresholds card (always visible for Admin) */}
            <div className="eco-card">
              <div className="eco-card-head">
                <h3>
                  <FaSlidersH className="eco-icon-sm" /> Thresholds
                </h3>
              </div>
              <p className="eco-muted">
                Visual controls for anomaly sensitivity (design only for now; wiring to backend can
                come later).
              </p>
              <div className="eco-slider">
                <label>
                  Isolation Forest Threshold <span>0.78</span>
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.01"
                  defaultValue="0.78"
                />
              </div>
              <div className="eco-slider">
                <label>
                  Autoencoder Threshold <span>0.74</span>
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.01"
                  defaultValue="0.74"
                />
              </div>
              <div className="eco-actions">
                <button className="btn-eco">Save Thresholds</button>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;
