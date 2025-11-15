import { useEffect, useMemo, useState } from 'react';
import { suggest, assignVisit, Suggestion } from '../../api/scheduling';
import { listCases, Case } from '../../api/cases';

export default function SuggestAssignTab(){
  const [caseId,setCaseId]=useState<number|''>(''); const [lat,setLat]=useState(''); const [lng,setLng]=useState('');
  const [strategy,setStrategy]=useState<'proximity'|'workload'>('proximity'); const [topK,setTopK]=useState(5);
  const [list,setList]=useState<Suggestion[]>([]);
  const [start,setStart]=useState(''); const [end,setEnd]=useState('');
  const [cases,setCases]=useState<Case[]>([]);
  const [assignError,setAssignError]=useState<string | null>(null);

  useEffect(()=>{
    let mounted=true;
    listCases()
      .then(data=>{ if(mounted) setCases(data); })
      .catch(err=>console.error('Failed to load cases for assignment', err));
    return ()=>{ mounted=false; };
  },[]);

  const doSuggest=async()=>{
    const req:any={strategy,top_k:topK};
    if(caseId!=='') req.case_id=Number(caseId);
    if(lat.trim()!==''&&lng.trim()!==''){ req.lat=parseFloat(lat); req.lng=parseFloat(lng); }
    setList(await suggest(req));
  };
  const caseOptions = useMemo(() => cases.map(c => ({
    id: c.id,
    label: `Case #${c.id}${c.district ? ` • ${c.district}` : ''} (${c.status})`
  })), [cases]);

  const doAssign=async(id:number)=>{
    if(caseId===''){ setAssignError('Pick a case before assigning.'); return; }
    if(!start||!end){ setAssignError('Pick start and end times.'); return; }
    setAssignError(null);
    try {
      await assignVisit({case_id:Number(caseId), inspector_id:id, start_time:new Date(start).toISOString(), end_time:new Date(end).toISOString()});
      alert('Appointment created.');
    } catch (err:any) {
      const detail = err?.response?.data?.detail || err?.message || 'Failed to assign';
      setAssignError(detail);
      console.error('Assign failed', err);
    }
  };
  
  return (
    <div className="eco-grid two">
      <div className="eco-card">
        <div className="eco-card-head"><h3>Suggest</h3></div>
        <div className="grid grid-cols-2 gap-3">
          <label className="col-span-2">Case ID 
            <input className="eco-input" list="case-id-options" value={caseId} onChange={e=>{
              const val=e.target.value;
              if(val===''){ setCaseId(''); return; }
              const parsed=Number(val);
              setCaseId(Number.isFinite(parsed)?parsed:'' );
            }}/>
            <datalist id="case-id-options">
              {caseOptions.map(opt=>(
                <option key={opt.id} value={String(opt.id)}>{opt.label}</option>
              ))}
            </datalist>
          </label>
          <label>Lat <input className="eco-input" value={lat} onChange={e=>setLat(e.target.value)}/></label>
          <label>Lng <input className="eco-input" value={lng} onChange={e=>setLng(e.target.value)}/></label>
          <label>Strategy
            <select className="eco-input" value={strategy} onChange={e=>setStrategy(e.target.value as any)}>
              <option value="proximity">Proximity</option>
              <option value="workload">Current load</option>
            </select>
          </label>
          <label>Top K <input className="eco-input" type="number" min={1} max={10} value={topK} onChange={e=>setTopK(Number(e.target.value))}/></label>
        </div>
        <div className="mt-3"><button className="btn-eco" onClick={doSuggest}>Suggest</button></div>
        {assignError && <p className="text-sm text-red-600 mt-2">{assignError}</p>}

        {list.length>0 && (
          <div className="eco-table compact mt-4">
            <div className="eco-thead"><span>Inspector</span><span>Score</span><span>Reason</span><span>Assign</span></div>
            {list.map(s=>(
              <div className="eco-row" key={s.inspector_id}>
                <span>{s.inspector_name}</span><span>{s.score}</span><span className="text-slate-500">{s.reason}</span>
                <span><button className="btn-eco sm" onClick={()=>doAssign(s.inspector_id)}>Assign</button></span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="eco-card">
        <div className="eco-card-head"><h3>New Appointment Window</h3></div>
        <label>Start <input type="datetime-local" className="eco-input" value={start} onChange={e=>setStart(e.target.value)}/></label>
        <label className="mt-2 block">End <input type="datetime-local" className="eco-input" value={end} onChange={e=>setEnd(e.target.value)}/></label>
        <p className="text-sm text-slate-500 mt-2">Pick times, then click <em>Assign</em> on a suggestion.</p>
      </div>
    </div>
  );
}
