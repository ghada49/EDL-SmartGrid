// frontend/src/pages/manager/InferenceTab.tsx
import React, { useMemo, useState } from "react";
import { api } from "../../api/client";
import { FaBolt, FaUpload, FaInfoCircle, FaCheckCircle } from "react-icons/fa";

type InferenceResult = {
  rank: number;
  FID?: string | number;
  BuildingID?: string | number;
  building_id?: number | null;
  fused_score: number;
  case_id?: number | null;
};

export default function InferenceTab() {
  const [file, setFile] = useState<File | null>(null);
  const [topPercent, setTopPercent] = useState<number>(5);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<InferenceResult[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!file) return;
    setError(null);
    setResults(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("top_percent", String(topPercent));

    setLoading(true);
    try {
      const res = await api.post("/ops/infer-and-create-cases", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResults(res.data.anomalies ?? []);
    } catch (err: any) {
      console.error(err);
      const msg =
        err?.response?.data?.detail ||
        err?.message ||
        "Inference failed. Please check the file and try again.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleTopChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = Number(e.target.value);
    if (Number.isNaN(v)) return;
    if (v < 1) return setTopPercent(1);
    if (v > 50) return setTopPercent(50);
    setTopPercent(v);
  };

  const selectedFileLabel = useMemo(() => {
    if (!file) return "No file selected";
    return `${file.name} (${Math.round(file.size / 1024)} KB)`;
  }, [file]);

  return (
    <div className="eco-card inference-card">
      <div className="eco-card-head flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="eco-pill">
            <FaBolt className="eco-icon-sm" /> Inference
          </div>
          <div>
            <h3>Score New Dataset</h3>
            <p className="eco-muted text-sm">
              Upload a CSV or Excel snapshot and auto-create cases from the top anomalies.
            </p>
          </div>
        </div>
        <div className="eco-badge glassy">{loading ? "Running..." : "Ready"}</div>
      </div>

      <div className="flex flex-col gap-4 md:flex-row md:items-stretch mt-2">
        {/* Upload button styled like Dataset Upload (btn-eco + hidden input) */}
        <div className="flex-1">
          <label className="block text-xs text-slate-600 mb-1">Dataset file</label>
          <label
            className="btn-eco flex items-center gap-2 cursor-pointer"
            style={{ width: "100%", justifyContent: "flex-start" }}
          >
            <FaUpload className="eco-icon-sm" />
            <span>{file ? file.name : "Upload CSV/XLSX"}</span>
            <input
              type="file"
              accept=".csv,.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel"
              style={{ display: "none" }}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>
          <p className="eco-muted text-xs mt-1">{selectedFileLabel}</p>
        </div>

        {/* Top % anomalies */}
<div style={{ width: 220 }}>
  <label className="block text-xs text-slate-600 mb-1">Top X% anomalies</label>

  <div className="auth-input flex items-center gap-2">
    <input
      type="number"
      min={1}
      max={50}
      value={topPercent}
      onChange={handleTopChange}
      className="flex-1 bg-transparent outline-none"
      style={{ border: "none", padding: 0 }}
    />
    <span className="text-slate-600 text-sm">% </span>
  </div>

  <p className="eco-muted text-[11px] mt-1">
    Between 1 and 50. Default 5.
  </p>
</div>

      </div>

      <div className="flex gap-3 mt-3">
        <button
          className="btn-eco"
          onClick={handleSubmit}
          disabled={!file || loading}
          style={{ minWidth: 220 }}
        >
          {loading ? "Scoring & creating cases..." : "Run Inference & Create Cases"}
        </button>
        <div className="flex items-center gap-2 text-xs eco-muted">
          <FaInfoCircle />
          Upload a clean snapshot; top anomalies will be created as new cases.
        </div>
      </div>

      <div className="eco-kpi-strip mt-4">
        <div className="eco-kpi glassy">
          <div className="eco-kpi-num">{topPercent}%</div>
          <div className="eco-kpi-label">Cutoff</div>
        </div>
        <div className="eco-kpi glassy">
          <div className="eco-kpi-num">{results?.length ?? 0}</div>
          <div className="eco-kpi-label">Anomalies Returned</div>
        </div>
        <div className="eco-kpi glassy">
          <div className="eco-kpi-num">{file ? "1" : "0"}</div>
          <div className="eco-kpi-label">Files Selected</div>
        </div>
      </div>

      {error && (
        <div className="mt-4 p-3 rounded-lg bg-red-50 text-red-700 text-sm border border-red-200">
          {error}
        </div>
      )}

      {results && results.length > 0 && (
        <div className="mt-6">
          <div className="flex items-center gap-2 mb-2">
            <FaCheckCircle className="text-green-600" />
            <h4 className="font-semibold text-slate-700">Flagged anomalies</h4>
          </div>
          <div className="eco-table compact">
            <div className="eco-thead">
              <span>Rank</span>
              <span>FID</span>
              <span>Building</span>
              <span>Fused score</span>
              <span>Case ID</span>
            </div>
            {results.map((r, idx) => (
              <div key={idx} className="eco-row">
                <span>{r.rank}</span>
                <span>{r.FID ?? r.BuildingID ?? "--"}</span>
                <span>{r.building_id ?? "--"}</span>
                <span>{r.fused_score.toFixed(3)}</span>
                <span>{r.case_id ?? "--"}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {results && results.length === 0 && !error && (
        <div className="mt-4 text-sm text-slate-500">
          Inference ran successfully but no anomalies were returned.
        </div>
      )}
    </div>
  );
}
