// frontend/src/pages/InspectorRoutes.tsx
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import TopNav from "../components/TopNav";
import { useAuth } from "../context/AuthContext";
import { listCases, Case, updateCaseStatus, addCaseComment, uploadCaseAttachment, addMeterReading, getCaseDetail, submitInspectionReport } from "../api/cases";
import {
  FaMapMarkedAlt,
  FaRoute,
  FaClipboardCheck,
  FaFlag
} from "react-icons/fa";

const InspectorRoutes: React.FC = () => {
  const { user_id } = useAuth();
  const [myCases, setMyCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(false);
  const [noteByCase, setNoteByCase] = useState<Record<number, string>>({});
  const [readingByCase, setReadingByCase] = useState<Record<number, string>>({});
  const [openDetailId, setOpenDetailId] = useState<number | null>(null);
  const [detail, setDetail] = useState<any | null>(null);
  const [findingsByCase, setFindingsByCase] = useState<Record<number, string>>({});
  const [recoByCase, setRecoByCase] = useState<Record<number, string>>({});
  const [flashByCase, setFlashByCase] = useState<Record<number, string>>({});

  useEffect(() => {
    const load = async () => {
      if (!user_id) return;
      setLoading(true);
      try {
        const rows = await listCases({ inspector_id: user_id });
        setMyCases(rows);
      } catch (e) {
        // eslint-disable-next-line no-console
        console.error("Failed to load inspector cases", e);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [user_id]);
  const flagged = [
    { id: 342, if: 0.86, ae: 0.78, rank: 0.82 },
    { id: 118, if: 0.91, ae: 0.74, rank: 0.85 },
    { id: 507, if: 0.77, ae: 0.81, rank: 0.79 },
  ];

  return (
    <div className="eco-page">
      {/* Sticky eco navbar (same as Login/Signup/Citizen/Manager) */}
      <TopNav/>

      <header className="eco-hero">
        <h1 className="eco-title">Inspector Console</h1>
        <p className="eco-sub">
          Prioritize visits, view flagged buildings, and manage your cases.
        </p>
      </header>

      {/* Grid of inspector tools */}
      <section className="eco-grid inspector-grid">
        {/* ---- Flagged buildings ---- */}
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
                  <Link
                    to={`/cases/new?building=${r.id}`}
                    className="btn-outline sm"
                  >
                    Create Case
                  </Link>
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* ---- Today’s Route / Schedule ---- */}
        <div className="eco-card">
          <div className="eco-card-head">
            <h3>
              <FaRoute className="eco-icon-sm" /> Today’s Route
            </h3>
            <span className="eco-chip">Optimized</span>
          </div>

          <p className="eco-muted">
            Ordered by proximity and combined anomaly rank.
          </p>

          <ol className="eco-steps">
            <li>08:30 — #B342 (Mar Elias)</li>
            <li>10:15 — #B118 (Ain El Mreisse)</li>
            <li>12:00 — #B507 (Tariq El Jdide)</li>
          </ol>

          <div className="eco-actions">
            <button className="btn-eco">Download Route CSV</button>
            <Link to="/inspections/new" className="btn-outline">
              Assign Extra Stop
            </Link>
          </div>

          <div className="eco-map">
            <FaMapMarkedAlt size={28} />
            <span>Map placeholder — markers + polyline route</span>
          </div>
        </div>

        {/* ---- My Cases (quick stats) ---- */}
        <div className="eco-card inspector-cases">
          <div className="eco-card-head">
            <h3>
              <FaClipboardCheck className="eco-icon-sm" /> My Cases
            </h3>
          </div>

          <p className="eco-muted">
            Move cases across the workflow. Keep notes & attach photos.
          </p>

          {loading ? (
            <p>Loading my cases…</p>
          ) : (
            <>
              <div className="eco-kpi-strip">
                {(["New", "Scheduled", "Visited", "Reported", "Closed"] as const).map((st) => (
                  <div className="eco-kpi glassy" key={st}>
                    <div className="eco-kpi-num">{myCases.filter((c) => c.status === st).length}</div>
                    <div className="eco-kpi-label">{st}</div>
                  </div>
                ))}
              </div>

              {myCases.length > 0 && (
                <div className="eco-table compact cases-scroll" style={{ marginTop: 12 }}>
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
                        <span>{c.building_id ?? '-'}</span>
                        <span className="eco-actions" style={{ gap: 6 }}>
                          <select className="auth-input" defaultValue="" onChange={async (e)=>{ const v=e.target.value; if(!v) return; await updateCaseStatus(c.id, v); const rows = await listCases({ inspector_id: user_id! }); setMyCases(rows); e.currentTarget.value=''; }}>
                            <option value="">Update Status</option>
                            {['New','Scheduled','Visited','Reported','Closed'].map(s => (<option key={s} value={s}>{s}</option>))}
                          </select>
                          <button className="btn-outline sm" onClick={async ()=>{ setOpenDetailId(c.id === openDetailId ? null : c.id); if (c.id !== openDetailId){ try { setDetail(await getCaseDetail(c.id)); } catch(e){ console.error(e) } } }}>
                            {openDetailId === c.id ? 'Hide Log' : 'View Log'}
                          </button>
                        </span>
                      </div>
                      <div className="eco-row" style={{ background: '#f8faf8' }}>
                        <span>Note</span>
                        <span style={{ gridColumn: 'span 3' }}>
                          <input className="auth-input" placeholder="Add on-site observation" value={noteByCase[c.id]||''} onChange={(e)=> setNoteByCase({ ...noteByCase, [c.id]: e.target.value })} />
                          <button className="btn-eco sm" onClick={async ()=>{ const t = (noteByCase[c.id]||'').trim(); if(!t) return; await addCaseComment(c.id, t, 'inspector'); setNoteByCase({ ...noteByCase, [c.id]: '' }); setFlashByCase({ ...flashByCase, [c.id]: 'Note added' }); setTimeout(()=> setFlashByCase((m)=> ({ ...m, [c.id]: '' })), 2000); if(openDetailId===c.id){ try{ setDetail(await getCaseDetail(c.id)); }catch{}} }}>Add</button>
                        </span>
                      </div>
                      <div className="eco-row" style={{ background: '#f8faf8' }}>
                        <span>Photo</span>
                        <span style={{ gridColumn: 'span 3' }}>
                          <input id={`upload-${c.id}`} type="file" accept="image/*" style={{ display: 'none' }}
                            onChange={async (e)=>{ const f=e.target.files?.[0]; if(!f) return; await uploadCaseAttachment(c.id, f, 'inspector'); setFlashByCase({ ...flashByCase, [c.id]: 'Photo uploaded' }); setTimeout(()=> setFlashByCase((m)=> ({ ...m, [c.id]: '' })), 2000); if(openDetailId===c.id){ try{ setDetail(await getCaseDetail(c.id)); }catch{}} (e.currentTarget as HTMLInputElement).value=''; }}
                          />
                          <button className="btn-outline sm" onClick={()=> (document.getElementById(`upload-${c.id}`) as HTMLInputElement)?.click()}>Upload Photo</button>
                          {flashByCase[c.id] && <span style={{ marginLeft:8, color:'#2e7d32', fontWeight:600 }}>{flashByCase[c.id]}</span>}
                        </span>
                      </div>
                      <div className="eco-row" style={{ background: '#f8faf8' }}>
                        <span>Meter</span>
                        <span style={{ gridColumn: 'span 3' }}>
                          <input className="auth-input" placeholder="e.g., 12873" value={readingByCase[c.id]||''} onChange={(e)=> setReadingByCase({ ...readingByCase, [c.id]: e.target.value })} />
                          <button className="btn-outline sm" onClick={async ()=>{ const val = parseFloat(readingByCase[c.id]); if(Number.isNaN(val)) return; await addMeterReading(c.id, val, 'kWh', 'inspector'); setReadingByCase({ ...readingByCase, [c.id]: '' }); setFlashByCase({ ...flashByCase, [c.id]: 'Reading saved' }); setTimeout(()=> setFlashByCase((m)=> ({ ...m, [c.id]: '' })), 2000); if(openDetailId===c.id){ try{ setDetail(await getCaseDetail(c.id)); }catch{}} }}>Save</button>
                        </span>
                      </div>
                      {openDetailId === c.id && detail && (
                        <div className="eco-row" style={{ gridColumn: 'span 4', background:'#f3f7f3' }}>
                          <div className="eco-table compact" style={{ width: '100%' }}>
                            <div className="eco-thead">
                              <span>When</span>
                              <span>Actor</span>
                              <span>Action</span>
                              <span>Note</span>
                            </div>
                            {detail.activities?.slice().reverse().slice(0,10).map((a: any)=> (
                              <div className="eco-row" key={a.id}>
                                <span>{new Date(a.created_at).toLocaleString()}</span>
                                <span>{a.actor}</span>
                                <span>{a.action}</span>
                                <span>{a.note}</span>
                              </div>
                            ))}
                            <div className="eco-row" style={{ background:'#fff' }}>
                              <span>Findings</span>
                              <span style={{ gridColumn:'span 3' }}>
                                <textarea className="auth-input" rows={2} placeholder="On-site observations"
                                  value={findingsByCase[c.id]||''}
                                  onChange={(e)=> setFindingsByCase({ ...findingsByCase, [c.id]: e.target.value })}
                                />
                              </span>
                            </div>
                            <div className="eco-row" style={{ background:'#fff' }}>
                              <span>Recommendation</span>
                              <span style={{ gridColumn:'span 3' }}>
                                <textarea className="auth-input" rows={2} placeholder="Recommended action"
                                  value={recoByCase[c.id]||''}
                                  onChange={(e)=> setRecoByCase({ ...recoByCase, [c.id]: e.target.value })}
                                />
                                <button className="btn-eco sm" style={{ marginTop: 6 }}
                                  onClick={async ()=>{
                                    if(!user_id) return;
                                    const f = (findingsByCase[c.id]||'').trim();
                                    const r = (recoByCase[c.id]||'').trim();
                                    if(!f && !r) return;
                                    await submitInspectionReport(c.id, user_id, f, r);
                                    setFindingsByCase({ ...findingsByCase, [c.id]: '' });
                                    setRecoByCase({ ...recoByCase, [c.id]: '' });
                                    setFlashByCase({ ...flashByCase, [c.id]: 'Report submitted' });
                                    setTimeout(()=> setFlashByCase((m)=> ({ ...m, [c.id]: '' })), 2000);
                                    try{ setDetail(await getCaseDetail(c.id)); } catch{}
                                  }}
                                >Submit Report</button>
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
