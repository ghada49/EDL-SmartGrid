// frontend/src/pages/manager/InferenceTab.tsx
import React, { useState } from "react";
import { api } from '../../api/client';

const InferenceTab: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [topPercent, setTopPercent] = useState<number>(5);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any[] | null>(null);

  const handleSubmit = async () => {
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    formData.append("top_percent", String(topPercent));
    // optionally: created_by user id/email
    setLoading(true);
    try {
      const res = await api.post("/ops/infer-and-create-cases", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResults(res.data.anomalies);
    } catch (err) {
      console.error(err);
      // show toast or error banner
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="inference-tab">
      <h2>Score New Dataset</h2>
      <p>Upload a new CSV/Excel file and choose the top X% anomalies.</p>

      <input
        type="file"
        accept=".csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.ms-excel"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
      />

      <div>
        <label>Top X% anomalies:</label>
        <input
          type="number"
          min={1}
          max={50}
          value={topPercent}
          onChange={(e) => setTopPercent(Number(e.target.value))}
        />
      </div>

      <button onClick={handleSubmit} disabled={!file || loading}>
        {loading ? "Scoring..." : "Run Inference & Create Cases"}
      </button>

      {results && (
        <table>
          <thead>
            <tr>
              <th>Rank</th>
              <th>FID</th>
              <th>Building ID</th>
              <th>Fused Score</th>
              <th>Case ID</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r, idx) => (
              <tr key={idx}>
                <td>{r.rank}</td>
                <td>{r.FID ?? r.BuildingID ?? "-"}</td>
                <td>{r.building_id ?? "-"}</td>
                <td>{r.fused_score.toFixed(3)}</td>
                <td>{r.case_id ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default InferenceTab;
