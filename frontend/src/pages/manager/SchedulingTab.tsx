// src/pages/manager/SchedulingTab.tsx
import { useEffect, useMemo, useState } from 'react';
import {
  listAppointments,
  Appointment,
  reschedule,
  reassign,
  listInspectors,
  Inspector,
} from '../../api/scheduling';
import StatusBadge from '../../components/StatusBadge';

function startOfWeek(d: Date) {
  const copy = new Date(d);
  const offset = (copy.getDay() + 6) % 7; // week starts Monday
  copy.setHours(0, 0, 0, 0);
  copy.setDate(copy.getDate() - offset);
  return copy;
}

function endOfWeek(d: Date) {
  const start = startOfWeek(d);
  const end = new Date(start);
  end.setDate(end.getDate() + 6);
  end.setHours(23, 59, 59, 999);
  return end;
}

function fmt(value: string) {
  return new Date(value).toLocaleString('en-LB', { dateStyle: 'medium', timeStyle: 'short' });
}

export default function SchedulingTab() {
  const [when, setWhen] = useState(new Date());
  const [rows, setRows] = useState<Appointment[]>([]);
  const [inspectors, setInspectors] = useState<Inspector[]>([]);

  const weekStart = useMemo(() => startOfWeek(when), [when]);
  const weekEnd = useMemo(() => endOfWeek(when), [when]);

  const load = async () => {
    const [apts, ins] = await Promise.all([
      listAppointments({
        start: weekStart.toISOString().slice(0, 10),
        end: weekEnd.toISOString().slice(0, 10),
      }),
      listInspectors(true),
    ]);
    setRows(apts);
    setInspectors(ins);
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [when]);

  return (
    <div className="eco-card">
      <div className="eco-card-head flex items-center gap-3">
        <h3>Appointments</h3>
        <input
          type="date"
          value={when.toISOString().slice(0, 10)}
          onChange={e => setWhen(new Date(e.target.value))}
          className="eco-input w-[180px]"
        />
        <button className="btn-outline" onClick={() => setWhen(new Date())}>
          This week
        </button>
      </div>

      <div className="eco-table">
        <div className="eco-thead">
          <span>ID</span>
          <span>Status</span>
          <span>Case</span>
          <span>Inspector</span>
          <span>Start</span>
          <span>End</span>
          <span>Actions</span>
        </div>
        {rows.map(a => (
          <div key={a.id} className="eco-row">
            <span>{a.id}</span>
            <span>
              <StatusBadge status={a.status} />
            </span>
            <span>{a.case_id}</span>
            <span>{a.inspector_id ?? '—'}</span>
            <span>{fmt(a.start_time)}</span>
            <span>{fmt(a.end_time)}</span>
            <span className="flex gap-2">
              <button
                className="btn-outline sm"
                onClick={async () => {
                  const start = prompt('New start (YYYY-MM-DDTHH:mm):', a.start_time.slice(0, 16));
                  const end = prompt('New end (YYYY-MM-DDTHH:mm):', a.end_time.slice(0, 16));
                  if (!start || !end) return;
                  await reschedule(a.id, {
                    start_time: new Date(start).toISOString(),
                    end_time: new Date(end).toISOString(),
                  });
                  load();
                }}
              >
                Reschedule
              </button>
              <button
                className="btn-eco sm"
                onClick={async () => {
                  const options = inspectors.map(i => `${i.id}:${i.name}`).join(', ');
                  const response = prompt(
                    `Reassign to inspector id (choices: ${options})`,
                    a.inspector_id?.toString() || '',
                  );
                  const id = Number(response);
                  if (!Number.isFinite(id) || id <= 0) return;
                  await reassign(a.id, { inspector_id: id });
                  load();
                }}
              >
                Reassign
              </button>
            </span>
          </div>
        ))}
        {rows.length === 0 && (
          <div className="p-6 text-center text-slate-500">No appointments this week.</div>
        )}
      </div>
    </div>
  );
}
