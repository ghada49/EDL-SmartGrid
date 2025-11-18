import React, { useEffect, useState } from "react";
import { listUsers, updateUserRole, UserRow } from "../api/users";
import { useAuth } from "../context/AuthContext";
import TicketManagementPanel from "./TicketManagementPanel";

import { Tabs } from "../components/Tabs";
import OverviewTab from "./manager/OverviewTab";
import SchedulingTab from "./manager/SchedulingTab";
import SuggestAssignTab from "./manager/SuggestAssignTab";
import ReportingTab from "./manager/ReportingTab";
import FeedbackPanel from "../components/FeedbackPanel";

import { uploadDataset, getDatasetHistory, DQ } from "../api/ops";

import {
  listCases,
  assignInspector,
  getCaseDetail,
  reviewCase,
  addCaseComment,
  Case,
} from "../api/cases";

const CASE_STATUSES = ["New", "Scheduled", "Reported", "Closed"] as const;

const ManagerDashboard: React.FC = () => {
  const { role: myRole } = useAuth();

  // ===============================
  // USER MANAGEMENT (logic only)
  // ===============================
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

  // Promotion functions (logic only)
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

  // ===============================
  // CASE MANAGEMENT
  // ===============================
  const [cases, setCases] = useState<Case[]>([]);
  const [loadingCases, setLoadingCases] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string>("");
  const [filterInspector, setFilterInspector] = useState<string>("");

  const [detailId, setDetailId] = useState<number | null>(null);
  const [detail, setDetail] = useState<any | null>(null);

  const [commentNote, setCommentNote] = useState<string>("");

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
      console.error("Failed filtering cases:", err);
    } finally {
      setLoadingCases(false);
    }
  };

  // ===== Dataset (kept unchanged) =====
  const [uploadDQ, setUploadDQ] = useState<DQ | null>(null);
  const [drift, setDrift] = useState<any[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  // ===============================
  // TABS
  // ===============================
  const [tab, setTab] = useState<
    | "Overview"
    | "Scheduling"
    | "Suggest & Assign"
    | "Reporting"
    | "Tickets"
    | "Case Management"
  >("Overview");

  return (
    <div className="ms-home eco-page">
      <div className="page-shell">

        {/* HEADER */}
        <header className="eco-hero">
          <h1 className="eco-title">Manager Console</h1>
          <p className="eco-sub">
            Manage datasets, models, thresholds, tickets, and cases.
          </p>
        </header>

        {/* TABS */}
        <Tabs
          tabs={[
            "Overview",
            "Suggest & Assign",
            "Scheduling",
            "Reporting",
            "Tickets",
            "Case Management",
          ]}
          active={tab}
          onChange={(t) => setTab(t as any)}
        />

        {/* TAB CONTENT */}
        {tab === "Overview" && <OverviewTab />}
        {tab === "Suggest & Assign" && <SuggestAssignTab />}
        {tab === "Scheduling" && <SchedulingTab />}
        {tab === "Reporting" && <ReportingTab />}
        {tab === "Tickets" && <TicketManagementPanel />}

        {/* ================= CASE MANAGEMENT TAB ================= */}
        {tab === "Case Management" && (
          <section className="eco-grid two">
            <div className="eco-card">
              <div className="eco-card-head">
                <h3>Case Management Panel</h3>
              </div>

              {/* FILTERS */}
              <div className="eco-actions" style={{ gap: 8 }}>
                <select
                  className="auth-input"
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                >
                  <option value="">All Statuses</option>
                  {CASE_STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>

                <select
                  className="auth-input"
                  value={filterInspector}
                  onChange={(e) => setFilterInspector(e.target.value)}
                  style={{ marginTop: 8 }}
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
                <button className="btn-eco" onClick={loadCases} style={{ marginTop: 8 }}>
                  Reload Cases
                </button>
              </div>

              {/* CASE LIST */}
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
                        } catch (err) {
                          console.error(err);
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

                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* CASE MODAL */}
        {detailId && detail && (
          <div className="eco-modal">
            <div className="eco-modal-content">
              <button
                className="eco-modal-close"
                aria-label="Close case details"
                onClick={() => {
                  setDetailId(null);
                  setDetail(null);
                }}
              >
                &times;
              </button>
              <h3>Case #{detailId}</h3>

              <p>Status: {detail.status}</p>
              <p>
                Building: {detail.building?.id || "-"}
                {detail.building?.district ? (
                  <>
                    {" - "}District: {detail.building.district}
                  </>
                ) : null}
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
                    <span>{new Date(a.created_at).toLocaleString()}</span>
                    <span>{a.actor || "-"}</span>
                    <span>{a.action}</span>
                    <span>{a.note}</span>
                  </div>
                ))}
              </div>

              <h4>Report</h4>
              {detail.reports.length === 0 && (
                <p className="eco-muted">No inspection report has been submitted yet.</p>
              )}
              {detail.reports.length > 0 && (
                (() => {
                  const r = detail.reports[0];
                  const readings =
                    (detail.activities || []).filter(
                      (a: any) =>
                        a.action === "METER_READING" &&
                        (!r.created_at ||
                          !a.created_at ||
                          new Date(a.created_at) <= new Date(r.created_at))
                    ) || [];
                  const readingEntry =
                    readings.length > 0 ? readings[readings.length - 1] : null;

                  return (
                    <div
                      key={r.id}
                      className="eco-card glassy"
                      style={{ marginBottom: 12, padding: 16, boxShadow: "none" }}
                    >
                      {r.findings && (
                        <div style={{ marginBottom: 12 }}>
                          <p className="eco-muted">Findings</p>
                          <pre className="eco-pre" style={{ whiteSpace: "pre-wrap" }}>
                            {r.findings}
                          </pre>
                        </div>
                      )}
                      {r.recommendation && (
                        <div style={{ marginBottom: 12 }}>
                          <p className="eco-muted">Recommendation</p>
                          <pre className="eco-pre" style={{ whiteSpace: "pre-wrap" }}>
                            {r.recommendation}
                          </pre>
                        </div>
                      )}
                      {readingEntry && (
                        <p style={{ marginBottom: 12 }}>
                          <strong>Latest Meter Reading:</strong> {readingEntry.note}{" "}
                          {readingEntry.created_at
                            ? `(${new Date(readingEntry.created_at).toLocaleString()})`
                            : ""}
                        </p>
                      )}
                      {detail.attachments && detail.attachments.length > 0 && (
                        <div style={{ marginBottom: 12 }}>
                          <p className="eco-muted">Attachments</p>
                          <ul style={{ margin: 0, paddingLeft: 16 }}>
                            {detail.attachments.map((at: any) => (
                              <li key={at.id}>
                                {at.filename}{" "}
                                {at.uploaded_at
                                  ? `(${new Date(at.uploaded_at).toLocaleString()})`
                                  : ""}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      <FeedbackPanel
                        embeddedCaseId={detailId ?? undefined}
                        showLogs={false}
                        isClosed={detail.status === "Closed"}
                        onConfirmed={async () => {
                          await loadCases();
                          if (detailId) {
                            setDetail(await getCaseDetail(detailId));
                          }
                        }}
                      />
                    </div>
                  );
                })()
              )}

              {/* COMMENT */}
              <div className="eco-actions" style={{ marginTop: 8 }}>
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
                    await addCaseComment(detailId, commentNote, "manager");
                    setCommentNote("");
                    setDetail(await getCaseDetail(detailId));
                  }}
                >
                  Add Comment
                </button>
              </div>

            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ManagerDashboard;
