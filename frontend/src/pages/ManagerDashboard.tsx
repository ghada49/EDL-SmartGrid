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
import OverviewTab from "./manager/OverviewTab";
import SchedulingTab from "./manager/SchedulingTab";
import SuggestAssignTab from "./manager/SuggestAssignTab";
import ReportingTab from "./manager/ReportingTab";
import FeedbackPanel from "../components/FeedbackPanel";

import { uploadDataset, getDatasetHistory, DQ } from "../api/ops";

// ✅ Case Management API
import {
  listCases,
  updateCaseStatus,
  assignInspector,
  decideCase,
  getCaseDetail,
  reviewCase,
  addCaseComment,
  uploadCaseAttachment,
  createCase,
  Case,
} from "../api/cases";

const ManagerDashboard: React.FC = () => {
  const { role: myRole } = useAuth();

  // ───── User Management ─────
  const [users, setUsers] = useState<UserRow[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  const loadUsers = async () => {
    try {
      setUsers(await listUsers());
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

  // ───── Case Management ─────
  const [cases, setCases] = useState<Case[]>([]);
  const [loadingCases, setLoadingCases] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string>("");
  const [filterInspector, setFilterInspector] = useState<string>("");
  const [detailId, setDetailId] = useState<number | null>(null);
  const [detail, setDetail] = useState<any | null>(null);
  const [newAnomalyId, setNewAnomalyId] = useState<string>("");
  const [newCaseNotes, setNewCaseNotes] = useState<string>("");
  const [commentNote, setCommentNote] = useState<string>("");
  const [attachFile, setAttachFile] = useState<File | null>(null);

  const loadCases = async () => {
    setLoadingCases(true);
    try {
      const data = await listCases();
      setCases(data);
    } catch (err) {
      console.error("Failed to fetch cases:", err);
    } finally {
      setLoadingCases(false);
    }
  };

  useEffect(() => {
    loadCases();
  }, []);

  const applyCaseFilters = async () => {
    setLoadingCases(true);
    try {
      const params: Record<string, string | number> = {};
      if (filterStatus) params.status = filterStatus;
      if (filterInspector !== "") params.inspector_id = filterInspector;
      const data = await listCases(params);
      setCases(data);
    } catch (err) {
      console.error("Failed to apply filters:", err);
    } finally {
      setLoadingCases(false);
    }
  };

  // ───── Dataset ops (Admin) ─────
  const [uploadDQ, setUploadDQ] = useState<DQ | null>(null);
  const [drift, setDrift] = useState<
    Array<{ column: string; z_score: number; drift_flag: boolean; method?: string }>
  >([]);
  const [history, setHistory] = useState<
    Array<{ id: number; filename: string; rows: number; uploaded_at: string; status: string }>
  >([]);
  const [showHistory, setShowHistory] = useState<boolean>(false);

  // ───── Tabs ─────
  const [tab, setTab] = useState<
    "Overview" | "Scheduling" | "Suggest & Assign" | "Reporting" | "Feedback"
  >("Overview");

  return (
    <div className="ms-home">

      <div className="page-shell">
        <div className="eco-page">
          <header className="eco-hero">
            <h1 className="eco-title">Manager Console</h1>
            <p className="eco-sub">
              Manage users, datasets, models, thresholds, cases and audit logs.
            </p>
          </header>

          <Tabs
            tabs={["Overview", "Suggest & Assign", "Scheduling", "Reporting", "Feedback"]}
            active={tab}
            onChange={(t) => setTab(t as any)}
          />
          {tab === "Overview" && <OverviewTab />}
          {tab === "Suggest & Assign" && <SuggestAssignTab />}
          {tab === "Scheduling" && <SchedulingTab />}
          {tab === "Reporting" && <ReportingTab />}
          {tab === "Feedback" && <FeedbackPanel />}

          {/* KPI strip (kept same) */}
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
            {/* ── Case Management Panel ── */}
            <div className="eco-card">
              <div className="eco-card-head">
                <h3>Case Management Panel</h3>
              </div>

              {/* Create Case */}
              <div
                className="eco-actions"
                style={{
                  gap: 8,
                  display: "flex",
                  alignItems: "center",
                  flexWrap: "wrap",
                  marginBottom: 8,
                }}
              >
                <input
                  className="auth-input"
                  placeholder="Anomaly ID"
                  value={newAnomalyId}
                  onChange={(e) => setNewAnomalyId(e.target.value)}
                />
                <input
                  className="auth-input"
                  placeholder="Notes (optional)"
                  value={newCaseNotes}
                  onChange={(e) => setNewCaseNotes(e.target.value)}
                />
                <button
                  className="btn-outline"
                  onClick={async () => {
                    try {
                      await createCase({
                        anomaly_id: newAnomalyId ? Number(newAnomalyId) : undefined,
                        notes: newCaseNotes || undefined,
                        created_by: "manager",
                      });
                      setNewAnomalyId("");
                      setNewCaseNotes("");
                      await loadCases();
                    } catch (e: any) {
                      alert(`Create case failed: ${e?.message || e}`);
                    }
                  }}
                >
                  Create Case
                </button>
              </div>

              {/* Filters */}
              <div
                className="eco-actions"
                style={{
                  gap: 8,
                  display: "flex",
                  alignItems: "center",
                  flexWrap: "wrap",
                }}
              >
                <select
                  className="auth-input"
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                >
                  <option value="">All Statuses</option>
                  {["New", "Scheduled", "Visited", "Reported", "Closed"].map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
                <select
                  className="auth-input"
                  value={filterInspector}
                  onChange={(e) => setFilterInspector(e.target.value)}
                >
                  <option value="">Any Inspector</option>
                  {users
                    .filter((u) => u.role === "Inspector")
                    .map((u) => (
                      <option key={u.id} value={String(u.id)}>
                        {u.full_name || u.email}
                      </option>
                    ))}
                </select>
                <button className="btn-outline" onClick={applyCaseFilters}>
                  Apply Filters
                </button>
                <button className="btn-eco" onClick={loadCases}>
                  Reload Cases
                </button>
              </div>

              {loadingCases && <p>Loading cases...</p>}
              {cases.map((c) => (
                <div className="eco-row" key={c.id}>
                  <span>Case #{c.id}</span>
                  <span>Status: {c.status}</span>
                  <span>Inspector: {c.inspector_name || "-"}</span>

                  <div className="eco-actions">
                    <button
                      className="btn-outline sm"
                      onClick={async () => {
                        setDetailId(c.id);
                        try {
                          setDetail(await getCaseDetail(c.id));
                        } catch (e) {
                          console.error(e);
                        }
                      }}
                    >
                      View
                    </button>
                    <select
                      className="auth-input"
                      defaultValue=""
                      onChange={async (e) => {
                        const v = e.target.value;
                        if (!v) return;
                        try {
                          await updateCaseStatus(c.id, v);
                          await loadCases();
                        } catch (err) {
                          console.error(err);
                        }
                        e.currentTarget.value = "";
                      }}
                    >
                      <option value="">Change Status</option>
                      {["New", "Scheduled", "Visited", "Reported", "Closed"].map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                    <select
                      className="auth-input"
                      defaultValue=""
                      onChange={async (e) => {
                        const v = e.target.value;
                        if (!v) return;
                        await assignInspector(c.id, v);
                        await applyCaseFilters();
                        e.currentTarget.value = "";
                      }}
                    >
                      <option value="" disabled>
                        Assign Inspector
                      </option>
                      {users
                        .filter((u) => u.role === "Inspector")
                        .map((u) => (
                          <option key={u.id} value={String(u.id)}>
                            {u.full_name || u.email}
                          </option>
                        ))}
                    </select>
                    <button
                      className="btn-eco sm"
                      onClick={() => decideCase(c.id, "Fraud")}
                    >
                      Mark Fraud
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {/* ── User Management ── */}
            <div className="eco-card">
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
            </div>

            {/* ── Dataset Upload (Admin only, backend-connected) ── */}
            {myRole === "Admin" && (
              <div className="eco-card">
                <div className="eco-card-head">
                  <h3>
                    <FaDatabase className="eco-icon-sm" /> Dataset Upload
                  </h3>
                </div>
                <p className="eco-muted">
                  Upload CSV (schema checked). Versioning & drift report.
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
                          }
                          setShowHistory(false);
                          try {
                            setHistory(await getDatasetHistory());
                          } catch {
                            /* history optional */
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
                        setHistory(await getDatasetHistory());
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
                  <div
                    className="eco-table compact"
                    style={{ marginTop: 12 }}
                  >
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
                  <div
                    className="eco-table compact"
                    style={{ marginTop: 12 }}
                  >
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
                  <div
                    className="eco-table compact"
                    style={{ marginTop: 12 }}
                  >
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
                        <span>
                          {new Date(h.uploaded_at).toLocaleString()}
                        </span>
                        <span>{h.status}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

           


          </section>

          {/* Case Detail Modal overlay */}
          {detailId && detail && (
            <div className="eco-modal">
              <div className="eco-modal-content">
                <h3>Case #{detailId}</h3>
                <p>Status: {detail.status}</p>
                <p>Outcome: {detail.outcome || "-"}</p>
                <p>
                  Building: {detail.building?.id || "-"} District:{" "}
                  {detail.building?.district || "-"}
                </p>

                <h4>Activities</h4>
                <div className="eco-table compact">
                  <div className="eco-thead">
                    <span>When</span>
                    <span>Actor</span>
                    <span>Action</span>
                    <span>Note</span>
                  </div>
                  {detail.activities.map((a: any) => (
                    <div className="eco-row" key={a.id}>
                      <span>
                        {new Date(a.created_at).toLocaleString()}
                      </span>
                      <span>{a.actor}</span>
                      <span>{a.action}</span>
                      <span>{a.note}</span>
                    </div>
                  ))}
                </div>

                <h4>Reports</h4>
                <div className="eco-table compact">
                  <div className="eco-thead">
                    <span>ID</span>
                    <span>Status</span>
                    <span>Actions</span>
                  </div>
                  {detail.reports.map((r: any) => (
                    <div className="eco-row" key={r.id}>
                      <span>{r.id}</span>
                      <span>{r.status}</span>
                      <span className="eco-actions">
                        <button
                          className="btn-outline sm"
                          onClick={async () => {
                            try {
                              await reviewCase(
                                detailId,
                                r.id,
                                "Approve_Fraud"
                              );
                              setDetail(await getCaseDetail(detailId));
                            } catch (e) {
                              console.error(e);
                            }
                          }}
                        >
                          Approve Fraud
                        </button>
                        <button
                          className="btn-outline sm"
                          onClick={async () => {
                            try {
                              await reviewCase(
                                detailId,
                                r.id,
                                "Approve_NoIssue"
                              );
                              setDetail(await getCaseDetail(detailId));
                            } catch (e) {
                              console.error(e);
                            }
                          }}
                        >
                          Approve No Issue
                        </button>
                        <button
                          className="btn-outline sm"
                          onClick={async () => {
                            try {
                              await reviewCase(detailId, r.id, "Recheck");
                              setDetail(await getCaseDetail(detailId));
                            } catch (e) {
                              console.error(e);
                            }
                          }}
                        >
                          Recheck
                        </button>
                        <button
                          className="btn-outline sm"
                          onClick={async () => {
                            try {
                              await reviewCase(detailId, r.id, "Reject");
                              setDetail(await getCaseDetail(detailId));
                            } catch (e) {
                              console.error(e);
                            }
                          }}
                        >
                          Reject
                        </button>
                      </span>
                    </div>
                  ))}
                </div>

                <h4>Attachments</h4>
                <div className="eco-table compact">
                  <div className="eco-thead">
                    <span>ID</span>
                    <span>File</span>
                    <span>When</span>
                  </div>
                  {detail.attachments.map((at: any) => (
                    <div className="eco-row" key={at.id}>
                      <span>{at.id}</span>
                      <span>{at.filename}</span>
                      <span>
                        {new Date(at.uploaded_at).toLocaleString()}
                      </span>
                    </div>
                  ))}
                </div>

                <div
                  className="eco-actions"
                  style={{ marginTop: 8, gap: 8 }}
                >
                  <textarea
                    className="auth-input"
                    placeholder="Add comment"
                    value={commentNote}
                    onChange={(e) => setCommentNote(e.target.value)}
                  />
                  <button
                    className="btn-outline sm"
                    onClick={async () => {
                      if (!commentNote) return;
                      try {
                        await addCaseComment(
                          detailId,
                          commentNote,
                          "manager"
                        );
                        setCommentNote("");
                        setDetail(await getCaseDetail(detailId));
                      } catch (e) {
                        console.error(e);
                      }
                    }}
                  >
                    Add Comment
                  </button>
                </div>

                <div
                  className="eco-actions"
                  style={{ marginTop: 8, gap: 8 }}
                >
                  <input
                    type="file"
                    className="auth-input"
                    onChange={(e) =>
                      setAttachFile(e.target.files?.[0] || null)
                    }
                  />
                  <button
                    className="btn-outline sm"
                    onClick={async () => {
                      if (!attachFile) return;
                      try {
                        await uploadCaseAttachment(
                          detailId,
                          attachFile,
                          "manager"
                        );
                        setAttachFile(null);
                        setDetail(await getCaseDetail(detailId));
                      } catch (e) {
                        console.error(e);
                      }
                    }}
                  >
                    Upload Attachment
                  </button>
                </div>

                <div className="eco-actions" style={{ marginTop: 12 }}>
                  <button
                    className="btn-outline"
                    onClick={() => {
                      setDetailId(null);
                      setDetail(null);
                    }}
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ManagerDashboard;
