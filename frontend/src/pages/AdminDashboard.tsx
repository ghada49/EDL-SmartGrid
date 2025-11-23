import React, { useCallback, useEffect, useState } from "react";
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
import {
  startTraining,
  getTrainingStatus,
  getCurrentModelCard,
  getModelHistory,
  activateModelVersion,
} from "../api/opsTrain";
import { API_BASE_URL } from "../api/client";

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
  const [userSearch, setUserSearch] = useState("");

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

  const canDemote = (u: UserRow) =>
    myRole === "Admin" && (u.role === "Inspector" || u.role === "Manager");

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

  // ───── Training state ─────
  const [mode, setMode] = useState<"fast" | "moderate" | "slow" | "very_slow">(
    "moderate"
  );
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<any>(null);
  const [isStartingTraining, setIsStartingTraining] = useState(false);

  // Model registry (current + history)
  const [modelCard, setModelCard] = useState<any | null>(null);
  const [modelHistory, setModelHistory] = useState<any[]>([]);
  const [activatingVersion, setActivatingVersion] = useState<number | null>(null);
  const [activationError, setActivationError] = useState<string | null>(null);
  const formatMetric = useCallback((value: any, digits = 3) => {
    if (value === null || value === undefined) return "—";
    return typeof value === "number" ? value.toFixed(digits) : value;
  }, []);

  // ───── Dataset Upload / Drift / History ─────
  const [uploadDQ, setUploadDQ] = useState<DQ | null>(null);
  const [drift, setDrift] = useState<DriftRow[]>([]);
  const [history, setHistory] = useState<DatasetHistoryRow[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);

  // ───── Tabs ─────
  const [tab, setTab] = useState<
    "Overview" | "Users" | "Data & Models" | "Model Registry"
  >(
    "Overview"
  );
  const [zoomedImg, setZoomedImg] = useState<string | null>(null);
  // ───── Initial load of model card + model history ─────
  const refreshModelInfo = useCallback(async () => {
    try {
      const card = await getCurrentModelCard();
      setModelCard(card);
    } catch (err) {
      setModelCard(null);
      console.warn("No current model card yet:", err);
    }
    try {
      const hist = await getModelHistory();
      setModelHistory(hist || []);
    } catch (err) {
      console.warn("Failed to load model history:", err);
    }
  }, []);

  useEffect(() => {
    refreshModelInfo();
  }, [refreshModelInfo]);

  // ───── Training job polling ─────
  useEffect(() => {
    if (!jobId) return;

    let cancelled = false;

    const tick = async () => {
      try {
        const data = await getTrainingStatus(jobId);
        if (!cancelled) {
          setStatus(data);
          if (data.status === "completed") {
            await refreshModelInfo();
          }
        }
      } catch (err) {
        if (!cancelled) console.error("Failed to fetch training status:", err);
      }
    };

    tick();
    const id = window.setInterval(tick, 3000);

    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [jobId, refreshModelInfo]);

  if (!myRole) {
    return <div>Loading...</div>;
  }
  useEffect(() => {
  const fetchInitialHistory = async () => {
    try {
      const hist = await getDatasetHistory();
      setHistory(hist || []);
    } catch (err) {
      console.warn("Failed to load initial dataset history:", err);
    }
  };

  fetchInitialHistory();
}, []);



  // ───── Filtered users based on search ─────
  const filteredUsers = users.filter((u) => {
    if (!userSearch.trim()) return true;
    const q = userSearch.toLowerCase();
    const name = (u.full_name || "").toLowerCase();
    const email = (u.email || "").toLowerCase();
    return name.includes(q) || email.includes(q);
  });

  const sortedModelHistory = [...modelHistory].sort((a, b) => {
    const av = typeof a?.version === "number" ? a.version : 0;
    const bv = typeof b?.version === "number" ? b.version : 0;
    return bv - av;
  });

  // ───── Training handler ─────
  const handleStartTraining = async () => {
    if (isStartingTraining) return;
    try {
      setIsStartingTraining(true);
      setStatus({ status: "queued", stage: "queued", progress: 0 });

      const res = await startTraining(mode); // { job_id, status, mode }
      setJobId(res.job_id);
    } catch (err: any) {
      console.error("Failed to start training:", err);
      setStatus({
        status: "failed",
        error: err?.response?.data?.detail || err.message,
      });
    } finally {
      setIsStartingTraining(false);
    }
  };

  const handleActivateVersion = async (version: number) => {
    if (activatingVersion === version) return;
    try {
      setActivationError(null);
      setActivatingVersion(version);
      await activateModelVersion(version);
      await refreshModelInfo();
    } catch (err: any) {
      setActivationError(err?.response?.data?.detail || err.message);
    } finally {
      setActivatingVersion(null);
    }
  };

  return (
    <div className="ms-home eco-page">
      <div className="page-shell">
        {/* ── Hero header ── */}
        <header className="eco-hero">
          <h1 className="eco-title">Admin Console</h1>
          <p className="eco-sub">
            Central console to manage user roles, curate datasets, run model
  training jobs, and control which anomaly model is live in production.
          </p>
        </header>

        {/* ── Tabs strip ── */}
        <Tabs
          tabs={["Overview", "Users", "Data & Models", "Model Registry"]}
          active={tab}
          onChange={(t) => setTab(t as any)}
        />

        {/* ── KPI strip ── */}
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

        {/* ── Main grid ── */}
        <section className="eco-main-panel">
          <div className="eco-card eco-card--full">
            {/* ───────── Overview TAB ───────── */}
            {tab === "Overview" && (
              <>
                <div className="eco-card-head">
                  <h3>System Overview</h3>
                </div>
                <p className="eco-muted">
                  Use this dashboard to: assign and update user roles, upload new
  datasets and review data-quality / drift checks, launch and monitor
  training jobs, and inspect or activate specific model versions.
  Switch tabs to move between <strong>Users</strong>, <strong> Data &amp; Models</strong>, and the <strong>Model Registry</strong>.
                </p>
              </>
            )}

            {/* ───────── Users TAB ───────── */}
            {tab === "Users" && (
              <>
                <div className="eco-card-head">
                  <h3>
                    <FaShieldAlt className="eco-icon-sm" /> User Management
                  </h3>
                  <input
                    type="text"
                    placeholder="Search by name or email"
                    value={userSearch}
                    onChange={(e) => setUserSearch(e.target.value)}
                    style={{
                      marginLeft: "auto",
                      padding: "0.3rem 0.6rem",
                      borderRadius: 8,
                      border: "1px solid #a5d6a7",
                      fontSize: "0.9rem",
                    }}
                  />
                </div>

                <div className="eco-table compact">
                  <div className="eco-thead">
                    <span>Name</span>
                    <span>Email</span>
                    <span>Role</span>
                    <span>Actions</span>
                  </div>

                  {filteredUsers.map((u) => (
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
                        {canDemote(u) &&
                          (u.role === "Inspector" || u.role === "Manager") && (
                            <button
                              className="btn-eco sm"
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

            
            {/* ───────── Data & Models TAB ───────── */}
            {tab === "Data & Models" && (
              <>
                {/* Dataset upload */}
                <div className="eco-card-head">
                  <h3>
                    <FaDatabase className="eco-icon-sm" /> Dataset Upload
                  </h3>
                </div>
                <p className="eco-muted">
                  Upload CSV/XLSX (schema checked). The system keeps a versioned
                  history and runs data quality checks and drift detection.
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
                            // optional
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
                  {zoomedImg && (
  <div
    className="eco-lightbox"
    onClick={() => setZoomedImg(null)}
  >
    <div
      className="eco-lightbox-inner"
      onClick={(e) => e.stopPropagation()}
    >
      <img src={zoomedImg} alt="Zoomed diagnostic plot" />
    </div>
  </div>
)}

                </div>

                {/* Data Quality */}
                {uploadDQ && (
                  <>
                    {/* High-level stats */}
                    <div
                      className="eco-muted"
                      style={{ marginTop: 12, marginBottom: 8, fontSize: "0.9rem" }}
                    >
                      <div>
                        <strong>Rows:</strong> {uploadDQ.row_count}
                      </div>
                      <div>
                        <strong>Duplicate rows:</strong> {uploadDQ.duplicate_rows} (
                        {(uploadDQ.duplicate_fraction * 100).toFixed(1)}%)
                      </div>
                    </div>

                    {/* Per-column stats */}
                    <div className="eco-table compact">
                      <div className="eco-thead">
                        <span>Column</span>
                        <span>Missing (NaN)</span>
                        <span>Invalid (rules)</span>
                        <span>Effective missing</span>
                        <span>Outliers (IQR)</span>
                      </div>

                      {Object.entries(uploadDQ.columns).map(([colName, stats]) => (
                        <div className="eco-row" key={colName}>
                          <span>{colName}</span>
                          <span>{(stats.missing_fraction * 100).toFixed(1)}%</span>
                          <span>{(stats.invalid_fraction * 100).toFixed(1)}%</span>
                          <span>{(stats.effective_missing_fraction * 100).toFixed(1)}%</span>
                          <span>{(stats.iqr_outlier_fraction * 100).toFixed(1)}%</span>
                        </div>
                      ))}
                    </div>
                  </>
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

                {/* Dataset history */}
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
                        <span>
                          {new Date(h.uploaded_at).toLocaleString()}
                        </span>
                        <span>{h.status}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* ───── Model Diagnostics (static plots) ───── */}
                {modelCard && (
                  <div
                    style={{
                      marginTop: 24,
                      paddingTop: 16,
                      borderTop: "1px solid #e0e0e0",
                    }}
                  >
                    <h4 style={{ marginBottom: 8 }}>Model diagnostics</h4>
                    <p className="eco-muted" style={{ marginBottom: 16 }}>
                      Static visuals from the latest training job to help
                      interpret anomaly separation and method quality.
                    </p>

                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns:
                          "repeat(auto-fit, minmax(260px, 1fr))",
                        gap: 16,
                      }}
                    >
                      {/* PCA scatter */}
<div className="glassy eco-card" style={{ padding: 12 }}>
  <h5 style={{ marginBottom: 6 }}>PCA – Normal vs Anomalies</h5>
  <p
    className="eco-muted"
    style={{ fontSize: "0.8rem", marginBottom: 8 }}
  >
    2-D projection of latent features. Red points are
    flagged anomalies; blue are normal buildings.
  </p>
  <img
    src={`${API_BASE_URL}/static/current_pca_fused.png`}
    alt="PCA projection of fused model"
    onClick={() =>
      setZoomedImg(`${API_BASE_URL}/static/current_pca_fused.png`)
    }
    style={{
      width: "100%",
      height: "220px",
      objectFit: "contain",
      borderRadius: 8,
      cursor: "zoom-in",
    }}
  />
</div>

{/* Fused histogram */}
<div className="glassy eco-card" style={{ padding: 12 }}>
  <h5 style={{ marginBottom: 6 }}>Fused rank distribution</h5>
  <p
    className="eco-muted"
    style={{ fontSize: "0.8rem", marginBottom: 8 }}
  >
    Distribution of the fused anomaly score. The cutoff
    defines which fraction is flagged.
  </p>
  <img
    src={`${API_BASE_URL}/static/current_fused_hist.png`}
    alt="Histogram of fused rank"
    onClick={() =>
      setZoomedImg(`${API_BASE_URL}/static/current_fused_hist.png`)
    }
    style={{
      width: "100%",
      height: "220px",
      objectFit: "contain",
      borderRadius: 8,
      cursor: "zoom-in",
    }}
  />
</div>

{/* Method metrics */}
<div className="glassy eco-card" style={{ padding: 12 }}>
  <h5 style={{ marginBottom: 6 }}>Method metrics</h5>
  <p
    className="eco-muted"
    style={{ fontSize: "0.8rem", marginBottom: 8 }}
  >
    Silhouette, Dunn, and Davies–Bouldin scores per
    method and for the fused ensemble. Higher
    Silhouette and Dunn, lower DBI are better.
  </p>
  <img
    src={`${API_BASE_URL}/static/current_method_metrics.png`}
    alt="Unsupervised metrics per method"
    onClick={() =>
      setZoomedImg(
        `${API_BASE_URL}/static/current_method_metrics.png`
      )
    }
    style={{
      width: "100%",
      height: "220px",
      objectFit: "contain",
      borderRadius: 8,
      cursor: "zoom-in",
    }}
  />
</div>

                    </div>
                  </div>
                )}

                {/* ───────── Model Training Panel ───────── */}
                <hr style={{ margin: "24px 0", borderColor: "#e0e0e0" }} />

                <div className="eco-card-head">
                  <h3>
                    <FaSlidersH className="eco-icon-sm" /> Model Training
                  </h3>
                </div>
                <p className="eco-muted">
                  Launch background model training. Choose a mode (fast for quick
                  checks, moderate for ASHA-based tuning). Progress and the
                  latest model card are shown below.
                </p>

                <div
                  className="eco-actions"
                  style={{
                    display: "flex",
                    gap: 12,
                    alignItems: "center",
                    marginTop: 8,
                  }}
                >
                  <select
                    value={mode}
                    onChange={(e) =>
                      setMode(
                        e.target.value as
                          | "fast"
                          | "moderate"
                          | "slow"
                          | "very_slow"
                      )
                    }
                    style={{
                      padding: "0.35rem 0.6rem",
                      borderRadius: 8,
                      border: "1px solid #a5d6a7",
                      fontSize: "0.9rem",
                    }}
                    disabled={isStartingTraining || status?.status === "running"}
                  >
                    <option value="fast">Fast (dev / quick check)</option>
                    <option value="moderate">
                      Moderate (ASHA – recommended)
                    </option>
                    <option value="slow">Slow (extended search)</option>
                    <option value="very_slow">
                      Very slow (full grid search)
                    </option>
                  </select>

                  <button
                    className="btn-eco"
                    onClick={handleStartTraining}
                    disabled={isStartingTraining || status?.status === "running"}
                  >
                    {isStartingTraining
                      ? "Starting…"
                      : status?.status === "running"
                      ? "Training in progress…"
                      : "Start Training"}
                  </button>
                </div>

                {/* Job status + progress */}
{status && (
  <div style={{ marginTop: 10 }}>
    {/* Progress bar if we have a numeric progress */}
    {typeof status.progress === "number" && (
      <>
        <div
          style={{
            height: "10px",
            width: "100%",
            background: "#e0f2f1",
            borderRadius: 999,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              height: "100%",
              width: `${Math.round(status.progress * 100)}%`,
              background: "#2e7d32",
              transition: "width 0.4s ease",
            }}
          />
        </div>
        <div
          style={{
            marginTop: 4,
            fontSize: "0.85rem",
            display: "flex",
            justifyContent: "space-between",
          }}
        >
          <span>
            Stage:{" "}
            {status.stage
              ? String(status.stage).replace(/_/g, " ")
              : status.status}
          </span>
          <span>{Math.round(status.progress * 100)}%</span>
        </div>
      </>
    )}

    <div
      className="eco-muted"
      style={{ marginTop: 6, fontSize: "0.9rem" }}
    >
      <div>
        <strong>Job status:</strong> {status.status}
      </div>
      {status.result?.mode && (
        <div>Last training mode: {status.result.mode}</div>
      )}
      {status.result?.duration_sec && (
        <div>
          Duration: {status.result.duration_sec.toFixed(1)} sec
        </div>
      )}
      {status.error && (
        <div style={{ color: "#c62828" }}>
          Error: {String(status.error)}
        </div>
      )}
    </div>
  </div>
)}

{/* Current model card summary */}
                {modelCard && (
                  <div
                    className="eco-table compact"
                    style={{ marginTop: 16, fontSize: "0.9rem" }}
                  >
                    <div className="eco-thead">
                      <span>Field</span>
                      <span>Value</span>
                    </div>
                    <div className="eco-row">
                      <span>Model ID</span>
                      <span>{modelCard.model_id}</span>
                    </div>
                    <div className="eco-row">
                      <span>Version</span>
                      <span>{modelCard.version}</span>
                    </div>
                    <div className="eco-row">
                      <span>Trained at</span>
                      <span>
                        {modelCard.trained_at
                          ? new Date(modelCard.trained_at).toLocaleString()
                          : "—"}
                      </span>
                    </div>
                    <div className="eco-row">
                      <span>Training mode</span>
                      <span>{modelCard.mode}</span>
                    </div>
                    <div className="eco-row">
                      <span>Data</span>
                      <span>
                        {modelCard.data?.n_samples ?? "?"} rows,{" "}
                        {modelCard.data?.n_features ?? "?"} features
                      </span>
                    </div>
                    <div className="eco-row">
                      <span>Silhouette / Dunn / DBI</span>
                      <span>
                        {modelCard.metrics?.silhouette?.toFixed
                          ? modelCard.metrics.silhouette.toFixed(3)
                          : modelCard.metrics?.silhouette}{" "}
                        /{" "}
                        {modelCard.metrics?.dunn?.toFixed
                          ? modelCard.metrics.dunn.toFixed(3)
                          : modelCard.metrics?.dunn}{" "}
                        /{" "}
                        {modelCard.metrics?.dbi?.toFixed
                          ? modelCard.metrics.dbi.toFixed(3)
                          : modelCard.metrics?.dbi}
                      </span>
                    </div>
                    <div className="eco-row">
                      <span>Stability (bootstrap ρ / Jaccard / ARI)</span>
                      <span>
                        {modelCard.stability?.bootstrap_spearman_rho?.toFixed
                          ? modelCard.stability.bootstrap_spearman_rho.toFixed(3)
                          : modelCard.stability?.bootstrap_spearman_rho}{" "}
                        /{" "}
                        {modelCard.stability?.bootstrap_jaccard_at_k?.toFixed
                          ? modelCard.stability.bootstrap_jaccard_at_k.toFixed(3)
                          : modelCard.stability?.bootstrap_jaccard_at_k}{" "}
                        /{" "}
                        {modelCard.stability?.bootstrap_ari?.toFixed
                          ? modelCard.stability.bootstrap_ari.toFixed(3)
                          : modelCard.stability?.bootstrap_ari}
                      </span>
                    </div>
                  </div>
                )}





              </>
            )}

            {/* ───────── Audit TAB ───────── */}
            {tab === "Model Registry" && (
              <>
                <div className="eco-card-head">
                  <h3>
                    <FaBalanceScale className="eco-icon-sm" /> Model Registry
                  </h3>
                </div>
                <p className="eco-muted">
                  Track every training run, compare metrics, and decide which version powers production scoring.
                </p>
                {activationError && (
                  <div
                    style={{
                      marginTop: 12,
                      padding: "8px 12px",
                      borderRadius: 8,
                      background: "#ffebee",
                      color: "#c62828",
                    }}
                  >
                    {activationError}
                  </div>
                )}
                {modelCard ? (
                  <div
                    className="eco-table compact"
                    style={{ marginTop: 16, fontSize: "0.9rem" }}
                  >
                    <div className="eco-thead">
                      <span>Field</span>
                      <span>Value</span>
                    </div>
                    <div className="eco-row">
                      <span>Version</span>
                      <span>
                        v{modelCard.version}{" "}
                        {modelCard.is_active && (
                          <span className="eco-badge">Active</span>
                        )}
                      </span>
                    </div>
                    <div className="eco-row">
                      <span>Trained at</span>
                      <span>
                        {modelCard.trained_at
                          ? new Date(modelCard.trained_at).toLocaleString()
                          : "-"}
                      </span>
                    </div>
                    <div className="eco-row">
                      <span>Activated at</span>
                      <span>
                        {modelCard.activated_at
                          ? new Date(modelCard.activated_at).toLocaleString()
                          : "-"}
                      </span>
                    </div>
                    <div className="eco-row">
                      <span>Mode / Runtime</span>
                      <span>
                        {modelCard.mode} -- {" "}
                        {modelCard.duration_sec
                          ? `${modelCard.duration_sec.toFixed(1)}s`
                          : "-"}
                      </span>
                    </div>
                    <div className="eco-row">
                      <span>Dataset</span>
                      <span>
                        {modelCard.data?.n_samples ?? "?"} rows, {" "}
                        {modelCard.data?.n_features ?? "?"} features
                      </span>
                    </div>
                    <div className="eco-row">
                      <span>Silhouette / Dunn / DBI</span>
                      <span>
                        {formatMetric(modelCard.metrics?.silhouette)} / {" "}
                        {formatMetric(modelCard.metrics?.dunn)} / {" "}
                        {formatMetric(modelCard.metrics?.dbi)}
                      </span>
                    </div>
                    <div className="eco-row">
                      <span>Bootstrap (rho / J@k / ARI)</span>
                      <span>
                        {formatMetric(
                          modelCard.stability?.bootstrap_spearman_rho
                        )} {" "}/ {" "}
                        {formatMetric(
                          modelCard.stability?.bootstrap_jaccard_at_k
                        )} {" "}/ {formatMetric(
                          modelCard.stability?.bootstrap_ari
                        )}
                      </span>
                    </div>
                    <div className="eco-row">
                      <span>Seed / Noise rho</span>
                      <span>
                        {formatMetric(modelCard.stability?.seed_rho)} / {" "}
                        {formatMetric(modelCard.stability?.noise_rho)}
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="eco-muted" style={{ marginTop: 16 }}>
                    No trained model yet.
                  </div>
                )}
                {sortedModelHistory.length > 0 ? (
                  <div
                    className="eco-table compact"
                    style={{
                      marginTop: 20,
                      fontSize: "0.8rem",
                      overflowX: "auto",
                    }}
                  >
                    <div className="eco-thead">
                      <span>Version</span>
                      <span>Mode</span>
                      <span>Runtime (s)</span>
                      <span>Silhouette</span>
                      <span>Dunn</span>
                      <span>DBI</span>
                      <span>Spearman rho</span>
                      <span>Jaccard@k</span>
                      <span>ARI</span>
                      <span>Trained at</span>
                      <span>Action</span>
                    </div>
                    {sortedModelHistory.map((m) => {
                      const isActive =
                        Boolean(m.is_active) ||
                        (modelCard && m.version === modelCard.version);
                      return (
                        <div className="eco-row" key={m.version}>
                          <span>v{m.version}</span>
                          <span>{m.mode}</span>
                          <span>
                            {m.duration_sec
                              ? m.duration_sec.toFixed(1)
                              : "-"}
                          </span>
                          <span>{formatMetric(m.metrics?.silhouette)}</span>
                          <span>{formatMetric(m.metrics?.dunn)}</span>
                          <span>{formatMetric(m.metrics?.dbi)}</span>
                          <span>
                            {formatMetric(
                              m.stability?.bootstrap_spearman_rho
                            )}
                          </span>
                          <span>
                            {formatMetric(
                              m.stability?.bootstrap_jaccard_at_k
                            )}
                          </span>
                          <span>{formatMetric(m.stability?.bootstrap_ari)}</span>
                          <span>
                            {m.trained_at
                              ? new Date(m.trained_at).toLocaleString()
                              : "-"}
                          </span>

                          <span>
                            <button
                              className="btn-outline"
                              style={{ padding: "0.2rem 0.8rem" }}
                              onClick={() => handleActivateVersion(m.version)}
                              disabled={isActive || activatingVersion === m.version}
                            >
                              {isActive
                                ? "Active"
                                : activatingVersion === m.version
                                ? "Activating..."
                                : "Activate"}
                            </button>
                          </span>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="eco-muted" style={{ marginTop: 16 }}>
                    No history yet. Run training to log model versions.
                  </div>
                )}
                <div
                  style={{
                    marginTop: 24,
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
                    gap: 16,
                  }}
                >
                  
                </div>
              </>
            )}
          </div>
        </section>
      </div>
    </div>
  );
};

export default AdminDashboard;




