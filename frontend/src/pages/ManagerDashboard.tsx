import React, { useEffect, useMemo, useState } from "react";
import { listUsers, updateUserRole, UserRow } from "../api/users";
import { useAuth } from "../context/AuthContext";
import TicketManagementPanel from "./TicketManagementPanel";

import { Tabs } from "../components/Tabs";
import OverviewTab from "./manager/OverviewTab";
import SchedulingTab from "./manager/SchedulingTab";
import FeedbackPanel from "../components/FeedbackPanel";

import { uploadDataset, getDatasetHistory, DQ } from "../api/ops";

import {
  listCases,
  getCaseDetail,
  reviewCase,
  addCaseComment,
  Case,
  listCasesMap,
} from "../api/cases";
import FraudMap, { FraudPoint } from "../components/FraudMap";
import { assignVisit, suggest, Suggestion } from "../api/scheduling";

const CASE_STATUSES = ["New", "Pending", "Scheduled", "Reported", "Closed"] as const;

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

  // MAP tab
  const [mapPoints, setMapPoints] = useState<FraudPoint[]>([]);
  const [mapLoading, setMapLoading] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);

  // Suggest & Assign (moved into Case Management)
  const [assignModalOpen, setAssignModalOpen] = useState(false);
  const [assignCaseId, setAssignCaseId] = useState<number | null>(null);
  const [assignLat, setAssignLat] = useState("");
  const [assignLng, setAssignLng] = useState("");
  const [assignStrategy, setAssignStrategy] = useState<"proximity" | "workload">("proximity");
  const [assignTopK, setAssignTopK] = useState(5);
  const [assignStart, setAssignStart] = useState("");
  const [assignEnd, setAssignEnd] = useState("");
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [assignError, setAssignError] = useState<string | null>(null);

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
    | "Map"
    | "Reporting"
    | "Tickets"
    | "Case Management"
  >("Overview");

  const loadMapPoints = async () => {
    setMapLoading(true);
    setMapError(null);
    try {
      const data = await listCasesMap();
      setMapPoints(
        data.map((d) => ({
          case_id: d.case_id,
          building_id: d.building_id ?? null,
          lat: d.lat,
          lng: d.lng,
          status: d.status,
          outcome: d.outcome,
          feedback_label: d.feedback_label ?? null,
        }))
      );
    } catch (err: any) {
      setMapError(err?.message || "Failed to load map data.");
      setMapPoints([]);
    } finally {
      setMapLoading(false);
    }
  };

  useEffect(() => {
    loadMapPoints();
  }, []);

  const caseLabel = useMemo(
    () =>
      new Map(
        cases.map((c) => [
          c.id,
          `Case #${c.id}${c.district ? ` - ${c.district}` : ""} (${c.status})`,
        ])
      ),
    [cases]
  );

  const openAssignModal = (c: Case) => {
    setAssignCaseId(c.id);
    const match = mapPoints.find((p) => p.case_id === c.id);
    setAssignLat(match ? String(match.lat) : "");
    setAssignLng(match ? String(match.lng) : "");
    setAssignModalOpen(true);
    setAssignError(null);
    setSuggestions([]);
  };

  const closeAssignModal = () => {
    setAssignModalOpen(false);
    setAssignError(null);
    setSuggestions([]);
  };

  const doSuggest = async () => {
    if (assignCaseId == null) {
      setAssignError("No case selected to suggest for.");
      return;
    }
    const payload: any = { strategy: assignStrategy, top_k: assignTopK, case_id: assignCaseId };
    if (assignLat.trim() !== "" && assignLng.trim() !== "") {
      payload.lat = Number(assignLat);
      payload.lng = Number(assignLng);
    }
    try {
      setAssignError(null);
      setSuggestions(await suggest(payload));
    } catch (err: any) {
      setAssignError(err?.message || "Failed to fetch suggestions");
    }
  };

  const doAssign = async (inspectorId: number) => {
    if (assignCaseId == null) {
      setAssignError("Pick a case before assigning.");
      return;
    }
    if (!assignStart || !assignEnd) {
      setAssignError("Pick start and end times.");
      return;
    }

    setAssignError(null);
    try {
      const payload: any = {
        case_id: Number(assignCaseId),
        inspector_id: inspectorId,
        start_time: new Date(assignStart).toISOString(),
        end_time: new Date(assignEnd).toISOString(),
      };
      if (assignLat.trim() !== "" && assignLng.trim() !== "") {
        const parsedLat = Number(assignLat);
        const parsedLng = Number(assignLng);
        if (!Number.isNaN(parsedLat) && !Number.isNaN(parsedLng)) {
          payload.target_lat = parsedLat;
          payload.target_lng = parsedLng;
        }
      }

      await assignVisit(payload);
      await applyCaseFilters();
      alert("Appointment created.");
      closeAssignModal();
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || "Failed to assign";
      setAssignError(detail);
      console.error("Assign failed", err);
    }
  };

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
            "Scheduling",
            "Case Management",
            "Map",
            "Tickets",
          ]}
          active={tab}
          onChange={(t) => setTab(t as any)}
        />

        {/* TAB CONTENT */}
        {tab === "Overview" && <OverviewTab />}
        {tab === "Scheduling" && <SchedulingTab />}
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
                    <button className="btn-eco sm" onClick={() => openAssignModal(c)}>
                      Assign Inspector
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {tab === "Map" && (
          <div className="eco-card">
            <div className="eco-card-head flex items-center justify-between gap-3">
              <div>
                <h3>Cases Map</h3>
                <p className="eco-muted" style={{ margin: 0 }}>
                  All cases with coordinates. No routes or home base overlays.
                </p>
              </div>
              <button className="btn-outline sm" onClick={loadMapPoints} disabled={mapLoading}>
                {mapLoading ? "Loading..." : "Reload"}
              </button>
            </div>
            <FraudMap
              points={mapPoints}
              loading={mapLoading}
              error={mapError}
              homeCoords={null}
              showRoutes={false}
              showHomeBase={false}
            />
          </div>
        )}

        {/* Suggest & Assign modal (from former tab) */}
        {assignModalOpen && (
          <div className="eco-modal">
            <div className="eco-modal-content" style={{ maxWidth: 960 }}>
              <button
                className="eco-modal-close"
                aria-label="Close suggest and assign"
                onClick={closeAssignModal}
              >
                &times;
              </button>
              <h3 style={{ marginTop: 0 }}>
                Suggest & Assign {assignCaseId ? `(Case #${assignCaseId})` : ""}
              </h3>
              <div className="eco-grid two">
                <div className="eco-card" style={{ minHeight: "100%" }}>
                  <div className="eco-card-head">
                    <h3>Suggest</h3>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="col-span-2">
                      <p className="eco-muted" style={{ marginBottom: 4 }}>
                        Case
                      </p>
                      <div className="assign-pill">
                        {assignCaseId ? caseLabel.get(assignCaseId) || `Case #${assignCaseId}` : "--"}
                      </div>
                    </div>
                    <div className="col-span-2">
                      <p className="eco-muted" style={{ marginBottom: 4 }}>
                        Target coordinates
                      </p>
                      <div className="assign-pill">
                        {assignLat && assignLng
                          ? `${assignLat}, ${assignLng}`
                          : "No coordinates available for this case"}
                      </div>
                    </div>
                    <label>
                      Strategy
                      <select
                        className="eco-input"
                        value={assignStrategy}
                        onChange={(e) => setAssignStrategy(e.target.value as any)}
                      >
                        <option value="proximity">Proximity</option>
                        <option value="workload">Current load</option>
                      </select>
                    </label>
                    <label>
                      Top K
                      <input
                        className="eco-input"
                        type="number"
                        min={1}
                        max={10}
                        value={assignTopK}
                        onChange={(e) => setAssignTopK(Number(e.target.value))}
                      />
                    </label>
                  </div>
                  <div className="mt-3">
                    <button className="btn-eco" onClick={doSuggest}>
                      Suggest
                    </button>
                  </div>
                  {assignError && <p className="text-sm text-red-600 mt-2">{assignError}</p>}

                  {suggestions.length > 0 && (
                    <div className="eco-table compact mt-4">
                      <div className="eco-thead">
                        <span>Inspector</span>
                        <span>Score</span>
                        <span>Reason</span>
                        <span>Assign</span>
                      </div>
                      {suggestions.map((s) => (
                        <div className="eco-row" key={s.inspector_id}>
                          <span>{s.inspector_name}</span>
                          <span>{s.score}</span>
                          <span className="text-slate-500">{s.reason}</span>
                          <span>
                            <button className="btn-eco sm" onClick={() => doAssign(s.inspector_id)}>
                              Assign
                            </button>
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="eco-card">
                  <div className="eco-card-head">
                    <h3>New Appointment Window</h3>
                  </div>
                  <label>
                    Start
                    <input
                      type="datetime-local"
                      className="eco-input"
                      value={assignStart}
                      onChange={(e) => setAssignStart(e.target.value)}
                    />
                  </label>
                  <label className="mt-2 block">
                    End
                    <input
                      type="datetime-local"
                      className="eco-input"
                      value={assignEnd}
                      onChange={(e) => setAssignEnd(e.target.value)}
                    />
                  </label>
                  <p className="text-sm text-slate-500 mt-2">
                    Pick times, then click <em>Assign</em> on a suggestion.
                  </p>
                </div>
              </div>
            </div>
          </div>
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
