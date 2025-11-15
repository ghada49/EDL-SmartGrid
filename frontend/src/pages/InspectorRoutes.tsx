// frontend/src/pages/InspectorRoutes.tsx
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import TopNav from "../components/TopNav";
import { useAuth } from "../context/AuthContext";
import {
  FaMapMarkedAlt,
  FaRoute,
  FaClipboardCheck,
  FaFlag,
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

type InspectorSummary = {
  inspector_id: number;
  pending: number;
  accepted: number;
  visited: number;
  closed_cases: number;
  fraud_detected: number;
  visits_today: number;
};

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
  onChanged?: () => void;
};

const TodaySchedule: React.FC<TodayScheduleProps> = ({
  inspector,
  onRoutesChange,
  onRoutesLoadingChange,
  onChanged,
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
      onChanged?.();
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
      onChanged?.();
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
      onChanged?.();
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
      onChanged?.();
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

  // inspector profile + route/summary (from second file)
  const [profile, setProfile] = useState<InspectorProfile | null>(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [routesSnapshot, setRoutesSnapshot] = useState<RouteOut | null>(null);
  const [routesLoading, setRoutesLoading] = useState(false);
  const [summary, setSummary] = useState<InspectorSummary | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [homeLatInput, setHomeLatInput] = useState("");
  const [homeLngInput, setHomeLngInput] = useState("");
  const [homeSaving, setHomeSaving] = useState(false);
  const [homeStatus, setHomeStatus] = useState<string | null>(null);
  const [homeError, setHomeError] = useState<string | null>(null);

  // "My Cases" panel state (from first file)
  const [myCases, setMyCases] = useState<Case[]>([]);
  const [casesLoading, setCasesLoading] = useState(false);
  const [noteByCase, setNoteByCase] = useState<Record<number, string>>({});
  const [readingByCase, setReadingByCase] = useState<Record<number, string>>({});
  const [openDetailId, setOpenDetailId] = useState<number | null>(null);
  const [detail, setDetail] = useState<any | null>(null);
  const [findingsByCase, setFindingsByCase] = useState<Record<number, string>>({});
  const [recoByCase, setRecoByCase] = useState<Record<number, string>>({});
  const [flashByCase, setFlashByCase] = useState<Record<number, string>>({});

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

  // ---- load summary ----
  const loadSummary = async () => {
    try {
      setSummaryError(null);
      const res = await getJSON<InspectorSummary>("/inspector/reports/inspector");
      setSummary(res);
    } catch (e: any) {
      setSummary(null);
      setSummaryError(e.message || String(e));
    }
  };

  useEffect(() => {
    if (profile) {
      loadSummary();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile?.id]);

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

  const flagged = [
    { id: 342, if: 0.86, ae: 0.78, rank: 0.82 },
    { id: 118, if: 0.91, ae: 0.74, rank: 0.85 },
    { id: 507, if: 0.77, ae: 0.81, rank: 0.79 },
  ];

  return (
    <div className="eco-page">
      <TopNav />

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

      <section className="eco-grid">
        {/* ---- Flagged buildings (shared) ---- */}
        <div className="eco-card">
          <div className="eco-card-head">
            <h3>
              <FaFlag className="eco-icon-sm" /> Flagged Buildings
            </h3>
            <span className="eco-chip">Live</span>
          </div>

          <p className="eco-muted">
            Buildings flagged by anomaly models (Isolation Forest / Autoencoder).
            Filter by district or score to focus your route.
          </p>

          <div className="eco-table compact">
            <div className="eco-thead">
              <span>Building</span>
              <span>IF</span>
              <span>AE</span>
              <span>Rank</span>
              <span>Actions</span>
            </div>

            {flagged.map((r) => (
              <div className="eco-row" key={r.id}>
                <span>#B{r.id}</span>
                <span>{r.if.toFixed(2)}</span>
                <span>{r.ae.toFixed(2)}</span>
                <span>
                  <b>{r.rank.toFixed(2)}</b>
                </span>
                <span className="eco-actions">
                  <Link to={`/buildings/${r.id}`} className="btn-eco sm">
                    Profile
                  </Link>
                  <Link to={`/cases/new?building=${r.id}`} className="btn-outline sm">
                    Create Case
                  </Link>
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* ---- Today's schedule / calendar ---- */}
        <TodaySchedule
          inspector={profile}
          onRoutesChange={setRoutesSnapshot}
          onRoutesLoadingChange={setRoutesLoading}
          onChanged={loadSummary}
        />

        {/* ---- Route summary card ---- */}
        <RouteSummaryCard
          routes={routesSnapshot}
          loading={routesLoading}
          inspector={profile}
        />

        {/* ---- Inspector profile / home base ---- */}
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
                Used for proximity-based suggestions shown to managers. Leave blank if
                you do not wish to disclose your home location.
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
              <button
                className="btn-eco mt-4"
                onClick={saveHomeBase}
                disabled={homeSaving}
              >
                {homeSaving ? "Saving..." : "Save Home Location"}
              </button>
              {homeStatus && (
                <p className="text-green-700 mt-2 text-sm">{homeStatus}</p>
              )}
              {homeError && <p className="text-red-600 mt-2 text-sm">{homeError}</p>}
            </>
          )}
        </div>

        {/* ---- Performance summary ---- */}
        <div className="eco-card">
          <div className="eco-card-head">
            <h3>
              <FaClipboardCheck className="eco-icon-sm" /> My Performance
            </h3>
          </div>
          {!summary && !summaryError && <p className="eco-muted">Loading summary…</p>}
          {summaryError && <div className="eco-error">{summaryError}</div>}
          {summary && (
            <>
              <div className="eco-kpi-strip">
                <div className="eco-kpi glassy">
                  <div className="eco-kpi-num">{summary.visits_today}</div>
                  <div className="eco-kpi-label">Visits today</div>
                </div>
                <div className="eco-kpi glassy">
                  <div className="eco-kpi-num">{summary.pending}</div>
                  <div className="eco-kpi-label">Pending</div>
                </div>
                <div className="eco-kpi glassy">
                  <div className="eco-kpi-num">{summary.accepted}</div>
                  <div className="eco-kpi-label">Confirmed</div>
                </div>
                <div className="eco-kpi glassy">
                  <div className="eco-kpi-num">{summary.closed_cases}</div>
                  <div className="eco-kpi-label">Cases closed</div>
                </div>
              </div>
              <p className="eco-muted">
                Fraud confirmations logged: <strong>{summary.fraud_detected}</strong>
              </p>
            </>
          )}
        </div>

        {/* ---- My Cases panel (from the first file) ---- */}
        <div className="eco-card inspector-cases">
          <div className="eco-card-head">
            <h3>
              <FaClipboardCheck className="eco-icon-sm" /> My Cases
            </h3>
          </div>

          <p className="eco-muted">
            Move cases across the workflow. Keep notes & attach photos.
          </p>

          {casesLoading ? (
            <p>Loading my cases…</p>
          ) : (
            <>
              <div className="eco-kpi-strip">
                {(["New", "Scheduled", "Visited", "Reported", "Closed"] as const).map((st) => (
                  <div className="eco-kpi glassy" key={st}>
                    <div className="eco-kpi-num">
                      {myCases.filter((c) => c.status === st).length}
                    </div>
                    <div className="eco-kpi-label">{st}</div>
                  </div>
                ))}
              </div>

              {myCases.length > 0 && (
                <div
                  className="eco-table compact cases-scroll"
                  style={{ marginTop: 12 }}
                >
                  <div className="eco-thead">
                    <span>Case</span>
                    <span>Status</span>
                    <span>Building</span>
                    <span>Actions</span>
                  </div>
                  {myCases.map((c) => (
                    <React.Fragment key={c.id}>
                      <div className="eco-row">
                        <span>#{c.id}</span>
                        <span>{c.status}</span>
                        <span>{c.building_id ?? "-"}</span>
                        <span className="eco-actions" style={{ gap: 6 }}>
                          <select
                            className="auth-input"
                            defaultValue=""
                            onChange={async (e) => {
                              const v = e.target.value;
                              if (!v) return;
                              await updateCaseStatus(c.id, v);
                              if (!user_id) return;
                              const rows = await listCases({ inspector_id: user_id });
                              setMyCases(rows);
                              e.currentTarget.value = "";
                            }}
                          >
                            <option value="">Update Status</option>
                            {["New", "Scheduled", "Visited", "Reported", "Closed"].map((s) => (
                              <option key={s} value={s}>
                                {s}
                              </option>
                            ))}
                          </select>
                          <button
                            className="btn-outline sm"
                            onClick={async () => {
                              setOpenDetailId(c.id === openDetailId ? null : c.id);
                              if (c.id !== openDetailId) {
                                try {
                                  setDetail(await getCaseDetail(c.id));
                                } catch (e) {
                                  // eslint-disable-next-line no-console
                                  console.error(e);
                                }
                              }
                            }}
                          >
                            {openDetailId === c.id ? "Hide Log" : "View Log"}
                          </button>
                        </span>
                      </div>
                      <div className="eco-row" style={{ background: "#f8faf8" }}>
                        <span>Note</span>
                        <span style={{ gridColumn: "span 3" }}>
                          <input
                            className="auth-input"
                            placeholder="Add on-site observation"
                            value={noteByCase[c.id] || ""}
                            onChange={(e) =>
                              setNoteByCase({ ...noteByCase, [c.id]: e.target.value })
                            }
                          />
                          <button
                            className="btn-eco sm"
                            onClick={async () => {
                              const t = (noteByCase[c.id] || "").trim();
                              if (!t) return;
                              await addCaseComment(c.id, t, "inspector");
                              setNoteByCase({ ...noteByCase, [c.id]: "" });
                              setFlashByCase({
                                ...flashByCase,
                                [c.id]: "Note added",
                              });
                              setTimeout(
                                () =>
                                  setFlashByCase((m) => ({
                                    ...m,
                                    [c.id]: "",
                                  })),
                                2000
                              );
                              if (openDetailId === c.id) {
                                try {
                                  setDetail(await getCaseDetail(c.id));
                                } catch {
                                  // ignore
                                }
                              }
                            }}
                          >
                            Add
                          </button>
                        </span>
                      </div>
                      <div className="eco-row" style={{ background: "#f8faf8" }}>
                        <span>Photo</span>
                        <span style={{ gridColumn: "span 3" }}>
                          <input
                            id={`upload-${c.id}`}
                            type="file"
                            accept="image/*"
                            style={{ display: "none" }}
                            onChange={async (e) => {
                              const f = e.target.files?.[0];
                              if (!f) return;
                              await uploadCaseAttachment(c.id, f, "inspector");
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
                              if (openDetailId === c.id) {
                                try {
                                  setDetail(await getCaseDetail(c.id));
                                } catch {
                                  // ignore
                                }
                              }
                              (e.currentTarget as HTMLInputElement).value = "";
                            }}
                          />
                          <button
                            className="btn-outline sm"
                            onClick={() =>
                              (document.getElementById(
                                `upload-${c.id}`
                              ) as HTMLInputElement)?.click()
                            }
                          >
                            Upload Photo
                          </button>
                          {flashByCase[c.id] && (
                            <span
                              style={{
                                marginLeft: 8,
                                color: "#2e7d32",
                                fontWeight: 600,
                              }}
                            >
                              {flashByCase[c.id]}
                            </span>
                          )}
                        </span>
                      </div>
                      <div className="eco-row" style={{ background: "#f8faf8" }}>
                        <span>Meter</span>
                        <span style={{ gridColumn: "span 3" }}>
                          <input
                            className="auth-input"
                            placeholder="e.g., 12873"
                            value={readingByCase[c.id] || ""}
                            onChange={(e) =>
                              setReadingByCase({
                                ...readingByCase,
                                [c.id]: e.target.value,
                              })
                            }
                          />
                          <button
                            className="btn-outline sm"
                            onClick={async () => {
                              const val = parseFloat(readingByCase[c.id]);
                              if (Number.isNaN(val)) return;
                              await addMeterReading(c.id, val, "kWh", "inspector");
                              setReadingByCase({
                                ...readingByCase,
                                [c.id]: "",
                              });
                              setFlashByCase({
                                ...flashByCase,
                                [c.id]: "Reading saved",
                              });
                              setTimeout(
                                () =>
                                  setFlashByCase((m) => ({
                                    ...m,
                                    [c.id]: "",
                                  })),
                                2000
                              );
                              if (openDetailId === c.id) {
                                try {
                                  setDetail(await getCaseDetail(c.id));
                                } catch {
                                  // ignore
                                }
                              }
                            }}
                          >
                            Save
                          </button>
                        </span>
                      </div>
                      {openDetailId === c.id && detail && (
                        <div
                          className="eco-row"
                          style={{ gridColumn: "span 4", background: "#f3f7f3" }}
                        >
                          <div
                            className="eco-table compact"
                            style={{ width: "100%" }}
                          >
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
                                    {new Date(a.created_at).toLocaleString()}
                                  </span>
                                  <span>{a.actor}</span>
                                  <span>{a.action}</span>
                                  <span>{a.note}</span>
                                </div>
                              ))}
                            <div className="eco-row" style={{ background: "#fff" }}>
                              <span>Findings</span>
                              <span style={{ gridColumn: "span 3" }}>
                                <textarea
                                  className="auth-input"
                                  rows={2}
                                  placeholder="On-site observations"
                                  value={findingsByCase[c.id] || ""}
                                  onChange={(e) =>
                                    setFindingsByCase({
                                      ...findingsByCase,
                                      [c.id]: e.target.value,
                                    })
                                  }
                                />
                              </span>
                            </div>
                            <div className="eco-row" style={{ background: "#fff" }}>
                              <span>Recommendation</span>
                              <span style={{ gridColumn: "span 3" }}>
                                <textarea
                                  className="auth-input"
                                  rows={2}
                                  placeholder="Recommended action"
                                  value={recoByCase[c.id] || ""}
                                  onChange={(e) =>
                                    setRecoByCase({
                                      ...recoByCase,
                                      [c.id]: e.target.value,
                                    })
                                  }
                                />
                                <button
                                  className="btn-eco sm"
                                  style={{ marginTop: 6 }}
                                  onClick={async () => {
                                    if (!user_id) return;
                                    const f = (findingsByCase[c.id] || "").trim();
                                    const r = (recoByCase[c.id] || "").trim();
                                    if (!f && !r) return;
                                    await submitInspectionReport(
                                      c.id,
                                      user_id,
                                      f,
                                      r
                                    );
                                    setFindingsByCase({
                                      ...findingsByCase,
                                      [c.id]: "",
                                    });
                                    setRecoByCase({
                                      ...recoByCase,
                                      [c.id]: "",
                                    });
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
                                    try {
                                      setDetail(await getCaseDetail(c.id));
                                    } catch {
                                      // ignore
                                    }
                                  }}
                                >
                                  Submit Report
                                </button>
                              </span>
                            </div>
                          </div>
                        </div>
                      )}
                    </React.Fragment>
                  ))}
                </div>
              )}
            </>
          )}

          <div className="eco-actions">
            <Link to="/inspector" className="btn-eco">
              Open Case Board
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
};

export default InspectorRoutes;
