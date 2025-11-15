// src/pages/manager/OverviewTab.tsx
import { useEffect, useState } from 'react';
import { listInspectors, workload, Inspector, WorkloadItem } from '../../api/scheduling';

export default function OverviewTab() {
  const [ins, setIns] = useState<Inspector[]>([]);
  const [wl, setWl] = useState<WorkloadItem[]>([]);
  useEffect(()=>{ (async ()=>{ setIns(await listInspectors(true)); setWl(await workload()); })(); },[]);


  return (
    
    <div className="eco-grid two">
      <div className="eco-card">
        <div className="eco-card-head"><h3>Inspectors</h3></div>
        <div className="eco-table compact">
          <div className="eco-thead"><span>ID</span><span>Name</span><span>Active</span><span>Home</span></div>
          {ins.map(i=>(
            <div key={i.id} className="eco-row">
              <span>{i.id}</span>
              <span>{i.name}</span>
              <span>{i.active ? 'Yes' : 'No'}</span>
              <span>{i.home_lat ?? '—'} / {i.home_lng ?? '—'}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="eco-card">
        <div className="eco-card-head"><h3>Workload (this week)</h3></div>
        <div className="eco-table compact">
          <div className="eco-thead"><span>Inspector</span><span>Active cases</span><span>Appts this week</span></div>
          {wl.map(w=>(
            <div key={w.inspector_id} className="eco-row">
              <span>{w.inspector_name}</span>
              <span>{w.active_cases}</span>
              <span>{w.appointments_this_week}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
