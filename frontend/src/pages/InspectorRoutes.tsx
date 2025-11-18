// frontend/src/pages/InspectorRoutes.tsx
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import {
  FaMapMarkedAlt,
  FaRoute,
  FaClipboardCheck,
  FaCalendarCheck,
  FaFilePdf,
  FaFileExcel,
} from "react-icons/fa";

// ---- existing case API helpers (from the first file) ----
import {
  listCases,
  Case,
  updateCaseStatus,
  addCaseComment,
  uploadCaseAttachment,
  addMeterReading,
  getCaseDetail,
  submitInspectionReport,
} from "../api/cases";

// ---- local helper for inspector-specific endpoints (second file) ----
const API_BASE =
  (import.meta as any)?.env?.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function authHeaders() {
  const t = localStorage.getItem("token");
  return {
    "Content-Type": "application/json",
    ...(t ? { Authorization: `Bearer ${t}` } : {}),
  };
}

async function getJSON<T>(url: string, params?: Record<string, any>): Promise<T> {
  const q =
    params && Object.keys(params).length
      ? `?${new URLSearchParams(
          Object.entries(params).reduce((acc, [k, v]) => {
            if (v !== undefined && v !== null) acc[k] = String(v);
            return acc;
          }, {} as Record<string, string>)
        ).toString()}`
      : "";
  const res = await fetch(`${API_BASE}${url}${q}`, {
    method: "GET",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`GET ${url}: ${res.status}`);
  return (await res.json()) as T;
}

async function patchJSON<T>(url: string, body: any): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify(body ?? {}),
  });
  if (!res.ok) {
    const msg = await res.text();
    throw new Error(`PATCH ${url}: ${res.status} ${msg}`);
  }
  return (await res.json()) as T;
}

async function getBlob(url: string, params?: Record<string, any>): Promise<Blob> {
  const q =
    params && Object.keys(params).length
      ? `?${new URLSearchParams(
          Object.entries(params).reduce((acc, [k, v]) => {
            if (v !== undefined && v !== null) acc[k] = String(v);
            return acc;
          }, {} as Record<string, string>)
        ).toString()}`
      : "";
  const res = await fetch(`${API_BASE}${url}${q}`, {
    method: "GET",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`GET blob ${url}: ${res.status}`);
  return await res.blob();
}

// ---- inspector types (from second file) ----

type Appt = {
  id: number;
  case_id: number;
  start: string;
  end: string;
  status: "pending" | "accepted" | "rejected" | "visited" | "closed";
  lat?: number;
  lng?: number;
};

type RoutePoint = { id: number; lat: number; lng: number; case_id: number; start?: string };
type RouteOut = { clusters: RoutePoint[][]; ordered: RoutePoint[] };

type InspectorProfile = {
  id: number;
  name: string;
  active: boolean;
  home_lat?: number | null;
  home_lng?: number | null;
  user_id?: string | null;
};

type InspectorTab = "calendar" | "route" | "home" | "cases";

const INSPECTOR_CASE_STATUSES = ["Scheduled", "Reported"] as const;

// ---- date / formatting helpers ----

function isoDay(date = new Date()): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function fmtHM(iso: string) {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function fmtTimeMaybe(iso?: string) {
  if (!iso) return "--";
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ---- TodaySchedule component (from second file) ----

type TodayScheduleProps = {
  inspector: InspectorProfile | null;
  onRoutesChange?: (routes: RouteOut | null) => void;
  onRoutesLoadingChange?: (loading: boolean) => void;
};

const TodaySchedule: React.FC<TodayScheduleProps> = ({
  inspector,
  onRoutesChange,
  onRoutesLoadingChange,
}) => {
  const today = useMemo(() => isoDay(new Date()), []);
  const [selectedDay, setSelectedDay] = useState(today);
  const [items, setItems] = useState<Appt[]>([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!inspector) {
      setItems([]);
      setErr(null);
      onRoutesLoadingChange?.(false);
      onRoutesChange?.(null);
      return;
    }
    try {
      setErr(null);
      setLoading(true);
      onRoutesLoadingChange?.(true);
      const params: Record<string, string | number> = { inspector_id: inspector.id };
      if (selectedDay) params.day = selectedDay;
      const [schedule, route] = await Promise.all([
        getJSON<Appt[]>("/inspector/schedule", params),
        getJSON<RouteOut>("/inspector/routes", params),
      ]);
      setItems(schedule);
      onRoutesChange?.(route);
    } catch (e: any) {
      setErr(e.message || String(e));
      setItems([]);
      onRoutesChange?.(null);
    } finally {
      setLoading(false);
      onRoutesLoadingChange?.(false);
    }
  }, [inspector, onRoutesChange, onRoutesLoadingChange, selectedDay]);

  useEffect(() => {
    load();
  }, [load]);

  const respond = async (id: number, action: "accept" | "reject") => {
    try {
      setBusy(true);
      await patchJSON<Appt>(`/inspector/appointments/${id}/respond`, { action });
      await load();
    } catch (e: any) {
      alert(e.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const confirmVisit = async (id: number) => {
    try {
      setBusy(true);
      await patchJSON<Appt>(`/inspector/schedule/${id}/confirm`, { action: "confirm" });
      await load();
    } catch (e: any) {
      alert(e.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const markVisited = async (id: number) => {
    try {
      setBusy(true);
      await patchJSON<Appt>(`/inspector/schedule/${id}/confirm`, { action: "visited" });
      await load();
    } catch (e: any) {
      alert(e.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const rescheduleVisit = async (appt: Appt) => {
    const start = prompt("New start (YYYY-MM-DDTHH:mm)", appt.start.slice(0, 16));
    const end = prompt("New end (YYYY-MM-DDTHH:mm)", appt.end.slice(0, 16));
    if (!start || !end) return;
    try {
      setBusy(true);
      await patchJSON<Appt>(`/inspector/schedule/${appt.id}/confirm`, {
        action: "reschedule",
        start_time: new Date(start).toISOString(),
        end_time: new Date(end).toISOString(),
      });
      await load();
    } catch (e: any) {
      alert(e.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const downloadCasePdf = async (caseId: number) => {
    try {
      const blob = await getBlob(`/inspector/reports/case/${caseId}.pdf`);
      downloadBlob(blob, `case_${caseId}.pdf`);
    } catch (e: any) {
      alert(e.message || String(e));
    }
  };

  const downloadWeeklyXlsx = async () => {
    if (!inspector) return;
    try {
      const now = new Date();
      const day = now.getDay() || 7;
      const start = new Date(now);
      start.setDate(now.getDate() - (day - 1));
      const weekStart = isoDay(start);
      const blob = await getBlob(`/inspector/reports/weekly.xlsx`, {
        inspector_id: inspector.id,
        week_start: weekStart,
      });
      downloadBlob(blob, `weekly_visits_${weekStart}.xlsx`);
    } catch (e: any) {
      alert(e.message || String(e));
    }
  };

  return (
    <div className="eco-card">
      <div className="eco-card-head flex items-center gap-3 flex-wrap">
        <h3>
          <FaCalendarCheck className="eco-icon-sm" /> My Calendar (Today)
        </h3>
        <input
          type="date"
          className="eco-input w-[170px]"
          value={selectedDay}
          onChange={(e) => {
            const val = e.target.value;
            setSelectedDay(val || today);
          }}
          disabled={!inspector}
        />
        <button className="btn-outline sm" onClick={load} disabled={loading || !inspector}>
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {!inspector && (
        <p className="eco-muted">
          Your account is not linked to an inspector profile yet. Ask an admin to pair it.
        </p>
      )}

      {inspector && (
        <p className="eco-muted">
          Showing visits for <strong>{inspector.name}</strong>{" "}
          {selectedDay ? `(${selectedDay})` : ""}
        </p>
      )}

      {err && (
        <div className="eco-alert warn" style={{ marginBottom: 12 }}>
          {err}
        </div>
      )}

      <div className="eco-table compact">
        <div className="eco-thead">
          <span>Time</span>
          <span>Case</span>
          <span>Status</span>
          <span>Actions</span>
        </div>
        {(!inspector || items.length === 0) && (
          <div className="eco-row">
            <span>{loading ? "Loading..." : "No appointments"}</span>
            <span>--</span>
            <span>--</span>
            <span>--</span>
          </div>
        )}
        {inspector &&
          items.map((a) => (
            <div className="eco-row" key={a.id}>
              <span>
                {fmtHM(a.start)} - {fmtHM(a.end)}
              </span>
              <span>#{a.case_id}</span>
              <span>{a.status}</span>
              <span className="eco-actions" style={{ flexWrap: "wrap", gap: 6 }}>
                {a.status !== "closed" && (
                  <>
                    <button
                      className="btn-eco sm"
                      disabled={busy}
                      onClick={() => confirmVisit(a.id)}
                    >
                      Confirm
                    </button>
                    <button
                      className="btn-outline sm"
                      disabled={busy}
                      onClick={() => rescheduleVisit(a)}
                    >
                      Reschedule
                    </button>
                    <button
                      className="btn-outline sm"
                      disabled={busy}
                      onClick={() => markVisited(a.id)}
                    >
                      Mark Visited
                    </button>
                  </>
                )}
                {a.status === "pending" && (
                  <button
                    className="btn-outline sm"
                    disabled={busy}
                    onClick={() => respond(a.id, "reject")}
                  >
                    Reject
                  </button>
                )}
                <button className="btn-outline sm" onClick={() => downloadCasePdf(a.case_id)}>
                  <FaFilePdf />
                </button>
              </span>
            </div>
          ))}
      </div>

      <div className="eco-actions" style={{ marginTop: 12 }}>
        <button className="btn-outline" onClick={downloadWeeklyXlsx} disabled={!inspector}>
          <FaFileExcel style={{ marginRight: 6 }} />
          Export Weekly XLSX
        </button>
      </div>
    </div>
  );
};

// ---- RouteSummaryCard (from second file) ----

const RouteSummaryCard: React.FC<{
  routes: RouteOut | null;
  loading: boolean;
  inspector: InspectorProfile | null;
}> = ({ routes, loading, inspector }) => {
  const hasVisits = !!routes && routes.ordered.length > 0;

  const downloadCsv = () => {
    if (!routes || !routes.ordered.length) return;
    const header = "order,appointment_id,case_id,start_time\n";
    const rows = routes.ordered
      .map(
        (p, idx) =>
          `${idx + 1},${p.id},${p.case_id},${p.start ? new Date(p.start).toISOString() : ""}`
      )
      .join("\n");
    const blob = new Blob([header + rows], { type: "text/csv" });
    downloadBlob(blob, `route_${isoDay()}.csv`);
  };

  return (
    <div className="eco-card">
      <div className="eco-card-head">
        <h3>
          <FaRoute className="eco-icon-sm" /> Today's Route
        </h3>
        <span className="eco-chip">
          {loading ? "Refreshing" : hasVisits ? "Optimized" : "Idle"}
        </span>
      </div>

      {!inspector && (
        <p className="eco-muted">Link this login to an inspector to see optimized routes.</p>
      )}

      {inspector && (
        <>
          {loading && <p className="eco-muted">Crunching route for {inspector.name}...</p>}
          {!loading && !hasVisits && (
            <p className="eco-muted">No visits scheduled for today. Enjoy the breather!</p>
          )}
          {hasVisits && routes && (
            <>
              <p className="eco-muted">
                Ordered by proximity + start time for <strong>{inspector.name}</strong>.
              </p>
              <ol className="eco-steps">
                {routes.ordered.map((stop, idx) => (
                  <li key={stop.id}>
                    {idx + 1}. {fmtTimeMaybe(stop.start)} — Case #{stop.case_id} (appt {stop.id})
                  </li>
                ))}
              </ol>

              {routes.clusters.length > 0 && (
                <>
                  <h4>Grouped Nearby Stops</h4>
                  <ol className="eco-steps">
                    {routes.clusters.map((cluster, idx) => (
                      <li key={idx}>
                        Cluster {idx + 1}: {cluster.map((p) => `#${p.case_id}`).join(", ")}
                      </li>
                    ))}
                  </ol>
                </>
              )}
            </>
          )}

          <div className="eco-actions">
            <button className="btn-eco" onClick={downloadCsv} disabled={!hasVisits}>
              Download Route CSV
            </button>
            <Link to="/inspections/new" className="btn-outline">
              Assign Extra Stop
            </Link>
          </div>

          <div className="eco-map">
            <FaMapMarkedAlt size={28} />
            <span>
              {hasVisits
                ? `${routes?.ordered.length ?? 0} stop(s) ready to plot on the map.`
                : "Map will render once you have visits."}
            </span>
          </div>
        </>
      )}
    </div>
  );
};

// ---- MAIN PAGE COMPONENT (merged) ----

const InspectorRoutes: React.FC = () => {
  const { role, user_id } = useAuth(); // need both: role (new) + user_id (old myCases API)

  // inspector profile + route state (from second file)
  const [profile, setProfile] = useState<InspectorProfile | null>(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [routesSnapshot, setRoutesSnapshot] = useState<RouteOut | null>(null);
  const [routesLoading, setRoutesLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<InspectorTab>("calendar");
  const [homeLatInput, setHomeLatInput] = useState("");
  const [homeLngInput, setHomeLngInput] = useState("");
  const [homeSaving, setHomeSaving] = useState(false);
  const [homeStatus, setHomeStatus] = useState<string | null>(null);
  const [homeError, setHomeError] = useState<string | null>(null);

  // "My Cases" panel state (from first file)
  const [myCases, setMyCases] = useState<Case[]>([]);
  const [casesLoading, setCasesLoading] = useState(false);
  const [openDetailId, setOpenDetailId] = useState<number | null>(null);
  const [detail, setDetail] = useState<any | null>(null);
  const [findingsByCase, setFindingsByCase] = useState<Record<number, string>>({});
  const [recoByCase, setRecoByCase] = useState<Record<number, string>>({});
  const [flashByCase, setFlashByCase] = useState<Record<number, string>>({});
  const [readingByCase, setReadingByCase] = useState<Record<number, string>>({});
  const [reportsByCase, setReportsByCase] = useState<
    Record<number, { findings?: string | null; recommendation?: string | null; submittedAt?: string | null } | null>
  >({});
  const reportsLoadingRef = useRef<Set<number>>(new Set());
  const [caseStatusFilter, setCaseStatusFilter] = useState<
    (typeof INSPECTOR_CASE_STATUSES)[number] | null
  >(null);

  const flashMessage = (caseId: number, message: string) => {
    setFlashByCase((prev) => ({ ...prev, [caseId]: message }));
    setTimeout(
      () =>
        setFlashByCase((prev) => ({
          ...prev,
          [caseId]: "",
        })),
      2000
    );
  };

  const autoLogReading = async (caseId: number) => {
    const readingValue = (readingByCase[caseId] || "").trim();
    if (!readingValue) return;
    const readingNumber = Number(readingValue);
    if (Number.isNaN(readingNumber)) {
      flashMessage(caseId, "Enter a valid reading");
      return;
    }
    try {
      await addMeterReading(caseId, readingNumber);
      setReadingByCase((prev) => ({ ...prev, [caseId]: "" }));
      flashMessage(caseId, "Reading logged");
    } catch (err: any) {
      flashMessage(caseId, err?.message || "Failed to log reading");
    }
  };

  useEffect(() => {
    myCases
      .filter((c) => c.status === "Reported" && reportsByCase[c.id] === undefined)
      .forEach((c) => {
        if (reportsLoadingRef.current.has(c.id)) return;
        reportsLoadingRef.current.add(c.id);
        (async () => {
          try {
            const detail = await getCaseDetail(c.id);
            const latest =
              detail?.reports && detail.reports.length
                ? detail.reports[detail.reports.length - 1]
                : null;
            setReportsByCase((prev) => ({
              ...prev,
              [c.id]: latest
                ? {
                    findings: latest.findings,
                    recommendation: latest.recommendation,
                    submittedAt: latest.created_at,
                  }
                : null,
            }));
          } catch {
            setReportsByCase((prev) => ({ ...prev, [c.id]: null }));
          } finally {
            reportsLoadingRef.current.delete(c.id);
          }
        })();
      });
  }, [myCases, reportsByCase]);

  // ---- load inspector profile ----
  useEffect(() => {
    let cancelled = false;
    const loadProfile = async () => {
      if (!role) {
        setProfileLoading(true);
        return;
      }
      if (role !== "Inspector") {
        setProfileLoading(false);
        setProfile(null);
        setProfileError("Only inspectors can access this console.");
        return;
      }
      try {
        setProfileLoading(true);
        const data = await getJSON<InspectorProfile>("/inspector/me");
        if (!cancelled) {
          setProfile(data);
          setProfileError(null);
        }
      } catch (e: any) {
        if (!cancelled) {
          setProfile(null);
          setProfileError(e.message || "Failed to load inspector profile");
        }
      } finally {
        if (!cancelled) setProfileLoading(false);
      }
    };
    loadProfile();
    return () => {
      cancelled = true;
    };
  }, [role]);

  useEffect(() => {
    if (profile) {
      setHomeLatInput(
        profile.home_lat === null || profile.home_lat === undefined
          ? ""
          : String(profile.home_lat)
      );
      setHomeLngInput(
        profile.home_lng === null || profile.home_lng === undefined
          ? ""
          : String(profile.home_lng)
      );
    }
  }, [profile?.home_lat, profile?.home_lng]);

  const saveHomeBase = async () => {
    if (!profile) return;
    setHomeError(null);
    setHomeStatus(null);

    const latVal =
      homeLatInput.trim() === "" ? null : Number(homeLatInput.trim());
    const lngVal =
      homeLngInput.trim() === "" ? null : Number(homeLngInput.trim());

    if (latVal !== null && Number.isNaN(latVal)) {
      setHomeError("Latitude must be a valid number.");
      return;
    }
    if (lngVal !== null && Number.isNaN(lngVal)) {
      setHomeError("Longitude must be a valid number.");
      return;
    }

    setHomeSaving(true);
    try {
      const updated = await patchJSON<InspectorProfile>("/inspector/me", {
        home_lat: latVal,
        home_lng: lngVal,
      });
      setProfile(updated);
      setHomeStatus("Home location saved.");
      setTimeout(() => setHomeStatus(null), 3000);
    } catch (e: any) {
      setHomeError(e.message || "Failed to save home location.");
    } finally {
      setHomeSaving(false);
    }
  };

  // ---- load "My Cases" list (from first file) ----
  useEffect(() => {
    const loadCases = async () => {
      if (!user_id) return;
      setCasesLoading(true);
      try {
        const rows = await listCases({ inspector_id: user_id });
        setMyCases(rows);
      } catch (e) {
        // eslint-disable-next-line no-console
        console.error("Failed to load inspector cases", e);
      } finally {
        setCasesLoading(false);
      }
    };
    loadCases();
  }, [user_id]);

  const calendarCard = (
    <TodaySchedule
      inspector={profile}
      onRoutesChange={setRoutesSnapshot}
      onRoutesLoadingChange={setRoutesLoading}
    />
  );

  const routeCard = (
    <RouteSummaryCard routes={routesSnapshot} loading={routesLoading} inspector={profile} />
  );

  const homeCard = (
    <div className="eco-card">
      <div className="eco-card-head">
        <h3>
          <FaMapMarkedAlt className="eco-icon-sm" /> Home Base
        </h3>
      </div>
      {!profile && (
        <p className="eco-muted">
          Sign in as an inspector to manage your profile and home coordinates.
        </p>
      )}
      {profile && (
        <>
          <p className="eco-muted">
            Used for proximity-based suggestions shown to managers. Leave blank if you do not
            wish to disclose your home location.
          </p>
          <label className="block mt-2">
            Latitude
            <input
              className="eco-input mt-1"
              type="number"
              step="0.0001"
              placeholder="33.8938"
              value={homeLatInput}
              onChange={(e) => setHomeLatInput(e.target.value)}
            />
          </label>
          <label className="block mt-3">
            Longitude
            <input
              className="eco-input mt-1"
              type="number"
              step="0.0001"
              placeholder="35.5018"
              value={homeLngInput}
              onChange={(e) => setHomeLngInput(e.target.value)}
            />
          </label>
          <button className="btn-eco mt-4" onClick={saveHomeBase} disabled={homeSaving}>
            {homeSaving ? "Saving..." : "Save Home Location"}
          </button>
          {homeStatus && <p className="text-green-700 mt-2 text-sm">{homeStatus}</p>}
          {homeError && <p className="text-red-600 mt-2 text-sm">{homeError}</p>}
        </>
      )}
    </div>
  );

  const filteredCases =
    caseStatusFilter == null ? myCases : myCases.filter((c) => c.status === caseStatusFilter);

  const casesCard = (
  <div className="eco-card inspector-cases">
      <div className="eco-card-head">
        <h3>
          <FaClipboardCheck className="eco-icon-sm" /> My Cases
        </h3>
      </div>

      <p className="eco-muted">Move cases across the workflow. Keep notes & attach photos.</p>

      {casesLoading ? (
        <p>Loading my cases…</p>
      ) : (
        <>
          <div className="eco-kpi-strip">
            {INSPECTOR_CASE_STATUSES.map((st) => {
              const count = myCases.filter((c) => c.status === st).length;
              const isActive = caseStatusFilter === st;
              return (
                <button
                  key={st}
                  type="button"
                  className={`eco-kpi glassy ${isActive ? "eco-kpi--active" : ""}`}
                  onClick={() => setCaseStatusFilter(isActive ? null : st)}
                >
                  <div className="eco-kpi-num">{count}</div>
                  <div className="eco-kpi-label">{st}</div>
                </button>
              );
            })}
          </div>

          {filteredCases.length > 0 ? (
            <div className="eco-table compact cases-scroll" style={{ marginTop: 12 }}>
              <div className="eco-thead">
                <span>Case</span>
                <span>Status</span>
                <span>Actions</span>
              </div>
              {filteredCases.map((c) => (
                <React.Fragment key={c.id}>
                  <div className="eco-row">
                    <span>#{c.id}</span>
                    <span>{c.status}</span>
                    <span className="eco-actions" style={{ gap: 6 }}>
                      <button
                        className="btn-outline sm"
                        onClick={async () => {
                          setOpenDetailId(c.id === openDetailId ? null : c.id);
                          if (c.id !== openDetailId) {
                            try {
                              setDetail(await getCaseDetail(c.id));
                            } catch (err) {
                              // eslint-disable-next-line no-console
                              console.error(err);
                            }
                          }
                        }}
                      >
                        {openDetailId === c.id ? "Hide Log" : "View Log"}
                      </button>
                    </span>
                  </div>
                  {c.status === "Reported" ? (
                    <div className="eco-row" style={{ background: "#f8faf8" }}>
                      <span>Submitted Report</span>
                      <span style={{ gridColumn: "span 3" }}>
                        {reportsByCase[c.id] === undefined ? (
                          <em>Loading submitted details…</em>
                        ) : reportsByCase[c.id] === null ? (
                          <em>No report data available.</em>
                        ) : (
                          <div>
                            <p style={{ marginBottom: 4 }}>
                              <strong>Findings:</strong>{" "}
                              {reportsByCase[c.id]?.findings || "—"}
                            </p>
                            <p style={{ marginBottom: 4 }}>
                              <strong>Recommendation:</strong>{" "}
                              {reportsByCase[c.id]?.recommendation || "—"}
                            </p>
                            {reportsByCase[c.id]?.submittedAt && (
                              <p style={{ fontSize: "0.85rem", color: "#4b5563" }}>
                                Submitted at{" "}
                                {new Date(
                                  reportsByCase[c.id]?.submittedAt as string
                                ).toLocaleString()}
                              </p>
                            )}
                          </div>
                        )}
                      </span>
                    </div>
                  ) : (
                    <>
                      <div className="eco-row" style={{ background: "#f8faf8" }}>
                        <span>Photo</span>
                        <span style={{ gridColumn: "span 3" }}>
                          <input
                            className="auth-input"
                            type="file"
                            accept="image/*"
                            onChange={async (e) => {
                              const file = e.target.files?.[0];
                              if (!file) return;
                              await uploadCaseAttachment(c.id, file, "inspector");
                              setFlashByCase({
                                ...flashByCase,
                                [c.id]: "Photo uploaded",
                              });
                              setTimeout(
                                () =>
                                  setFlashByCase((m) => ({
                                    ...m,
                                    [c.id]: "",
                                  })),
                                2000
                              );
                            }}
                          />
                        </span>
                      </div>
                      <div className="eco-row" style={{ background: "#f8faf8" }}>
                        <span>Meter</span>
                        <span style={{ gridColumn: "span 3" }}>
                          <input
                            className="auth-input"
                            placeholder="Reading"
                            value={readingByCase[c.id] || ""}
                            onChange={(e) =>
                              setReadingByCase({ ...readingByCase, [c.id]: e.target.value })
                            }
                            onBlur={() => autoLogReading(c.id)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") {
                                e.preventDefault();
                                autoLogReading(c.id);
                              }
                            }}
                          />
                        </span>
                      </div>
                      <div className="eco-row" style={{ background: "#f8faf8" }}>
                        <span>Fraud</span>
                        <span style={{ gridColumn: "span 3" }}>
                          <textarea
                            className="auth-input"
                            placeholder="Findings"
                            value={findingsByCase[c.id] || ""}
                            onChange={(e) =>
                              setFindingsByCase({ ...findingsByCase, [c.id]: e.target.value })
                            }
                          />
                          <textarea
                            className="auth-input mt-2"
                            placeholder="Recommendation"
                            value={recoByCase[c.id] || ""}
                            onChange={(e) =>
                              setRecoByCase({ ...recoByCase, [c.id]: e.target.value })
                            }
                          />
                          <button
                            className="btn-outline sm mt-2"
                            onClick={async () => {
                              const findings = (findingsByCase[c.id] || "").trim();
                              const recommendation = (recoByCase[c.id] || "").trim();
                              if (!findings && !recommendation) return;
                              if (!user_id) {
                                setFlashByCase({
                                  ...flashByCase,
                                  [c.id]: "Unable to submit report: missing user id",
                                });
                                setTimeout(
                                  () =>
                                    setFlashByCase((m) => ({
                                      ...m,
                                      [c.id]: "",
                                    })),
                                  2000
                                );
                                return;
                              }
                              await submitInspectionReport(c.id, {
                                inspector_id: user_id,
                                findings,
                                recommendation,
                              });
                              await updateCaseStatus(c.id, "Reported");
                              setReportsByCase((prev) => ({
                                ...prev,
                                [c.id]: {
                                  findings,
                                  recommendation,
                                  submittedAt: new Date().toISOString(),
                                },
                              }));
                              setFindingsByCase({ ...findingsByCase, [c.id]: "" });
                              setRecoByCase({ ...recoByCase, [c.id]: "" });
                              setFlashByCase({
                                ...flashByCase,
                                [c.id]: "Report submitted",
                              });
                              setTimeout(
                                () =>
                                  setFlashByCase((m) => ({
                                    ...m,
                                    [c.id]: "",
                                  })),
                                2000
                              );
                              if (user_id) {
                                const rows = await listCases({ inspector_id: user_id });
                                setMyCases(rows);
                              }
                            }}
                          >
                            Submit
                          </button>
                        </span>
                      </div>
                    </>
                  )}
                  {flashByCase[c.id] && (
                    <div
                      className="eco-row"
                      style={{ gridColumn: "span 4", background: "#ecfdf3" }}
                    >
                      <span style={{ gridColumn: "span 4" }}>{flashByCase[c.id]}</span>
                    </div>
                  )}
                  {openDetailId === c.id && detail && (
                    <div
                      className="eco-row"
                      style={{ gridColumn: "span 4", background: "#f3f7f3" }}
                    >
                      <div className="eco-table compact" style={{ width: "100%" }}>
                        <div className="eco-thead">
                          <span>When</span>
                          <span>Actor</span>
                          <span>Action</span>
                          <span>Note</span>
                        </div>
                        {detail.activities
                          ?.slice()
                          .reverse()
                          .slice(0, 10)
                          .map((a: any) => (
                            <div className="eco-row" key={a.id}>
                              <span>
                                {a.created_at ? new Date(a.created_at).toLocaleString() : "-"}
                              </span>
                              <span>{a.actor || "-"}</span>
                              <span>{a.action || "-"}</span>
                              <span>{a.note || "-"}</span>
                            </div>
                          ))}
                      </div>
                    </div>
                  )}
                </React.Fragment>
              ))}
            </div>
          ) : (
            <p className="eco-muted mt-3">
              {caseStatusFilter
                ? `No ${caseStatusFilter.toLowerCase()} cases right now.`
                : "No assigned cases yet."}
            </p>
          )}
        </>
      )}
    </div>
  );

  const tabItems: { id: InspectorTab; label: string; content: React.ReactNode }[] = [
    { id: "calendar", label: "My Calendar", content: calendarCard },
    { id: "route", label: "Today's Route", content: routeCard },
    { id: "home", label: "Home Base", content: homeCard },
    { id: "cases", label: "My Cases", content: casesCard },
  ];

  return (
    <div className="eco-page">

      <header className="eco-hero">
        <h1 className="eco-title">Inspector Console</h1>
        <p className="eco-sub">
          Prioritize visits, view flagged buildings, and manage your cases.
        </p>
      </header>

      {profileLoading && (
        <div className="eco-muted" style={{ marginBottom: 16 }}>
          Loading your inspector profile...
        </div>
      )}
      {profileError && (
        <div className="eco-alert warn" style={{ marginBottom: 16 }}>
          {profileError}
        </div>
      )}

      <div className="eco-tabs" role="tablist" aria-label="Inspector tools">
        {tabItems.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`eco-tab ${activeTab === tab.id ? "eco-tab--active" : ""}`}
            onClick={() => setActiveTab(tab.id)}
            role="tab"
            aria-selected={activeTab === tab.id}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="eco-tab-panels">
        {tabItems.map((tab) => (
          <div
            key={tab.id}
            className={`eco-tab-panel ${activeTab === tab.id ? "eco-tab-panel--active" : ""}`}
            role="tabpanel"
            hidden={activeTab !== tab.id}
          >
            {tab.content}
          </div>
        ))}
      </div>
    </div>
  );
};

export default InspectorRoutes;
