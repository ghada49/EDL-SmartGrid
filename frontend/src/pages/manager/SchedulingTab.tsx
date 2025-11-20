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
import React from 'react';

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
  const [busyId, setBusyId] = useState<number | null>(null);
  const [editApptId, setEditApptId] = useState<number | null>(null);
  const [editStart, setEditStart] = useState('');
  const [editEnd, setEditEnd] = useState('');
  const [reassignApptId, setReassignApptId] = useState<number | null>(null);
  const [selectedInspector, setSelectedInspector] = useState<string>('');

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

  const inspectorLabel = (id?: number | null) => {
    if (!id) return '—';
    const match = inspectors.find(i => i.id === id);
    return match ? `${match.name} (#${match.id})` : `#${id}`;
  };

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
        {rows.map(a => {
          const startLocal = new Date(a.start_time).toISOString().slice(0, 16);
          const endLocal = new Date(a.end_time).toISOString().slice(0, 16);
          const isEditing = editApptId === a.id;
          const isReassigning = reassignApptId === a.id;
          return (
            <React.Fragment key={a.id}>
              <div className="eco-row" style={{ alignItems: 'center' }}>
                <span>{a.id}</span>
                <span>
                  <StatusBadge status={a.status} />
                </span>
                <span>{a.case_id}</span>
                <span>{inspectorLabel(a.inspector_id)}</span>
                <span>
                  <div>{fmt(a.start_time)}</div>
                  <div className="eco-muted text-xs">Start</div>
                </span>
                <span>
                  <div>{fmt(a.end_time)}</div>
                  <div className="eco-muted text-xs">End</div>
                </span>
                <span className="flex gap-2 flex-wrap justify-end">
                  <button
                    className="btn-outline sm"
                    onClick={() => {
                      setReassignApptId(null);
                      setEditApptId(isEditing ? null : a.id);
                      setEditStart(startLocal);
                      setEditEnd(endLocal);
                    }}
                  >
                    Reschedule
                  </button>
                  <button
                    className="btn-eco sm"
                    onClick={() => {
                      setEditApptId(null);
                      setReassignApptId(isReassigning ? null : a.id);
                      setSelectedInspector(a.inspector_id ? String(a.inspector_id) : '');
                    }}
                  >
                    Reassign
                  </button>
                </span>
              </div>

              {isEditing && (
                <div className="eco-row" style={{ background: '#f8fafc' }}>
                  <span style={{ gridColumn: 'span 7' }}>
                    <div
                      className="flex flex-wrap gap-4 items-end"
                      style={{
                        padding: 12,
                        border: '1px solid #d9e3f0',
                        borderRadius: 12,
                        background: '#fff',
                      }}
                    >
                      <div>
                        <label className="block text-xs text-slate-600">Start</label>
                        <input
                          type="datetime-local"
                          className="eco-input"
                          value={editStart}
                          onChange={e => setEditStart(e.target.value)}
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-600">End</label>
                        <input
                          type="datetime-local"
                          className="eco-input"
                          value={editEnd}
                          onChange={e => setEditEnd(e.target.value)}
                        />
                      </div>
                      <div className="flex gap-2">
                        <button
                          className="btn-eco sm"
                          disabled={busyId === a.id}
                          onClick={async () => {
                            if (!editStart || !editEnd) return;
                            setBusyId(a.id);
                            try {
                              await reschedule(a.id, {
                                start_time: new Date(editStart).toISOString(),
                                end_time: new Date(editEnd).toISOString(),
                              });
                              await load();
                              setEditApptId(null);
                            } finally {
                              setBusyId(null);
                            }
                          }}
                        >
                          {busyId === a.id ? 'Saving...' : 'Save'}
                        </button>
                        <button className="btn-outline sm" onClick={() => setEditApptId(null)}>
                          Cancel
                        </button>
                      </div>
                    </div>
                  </span>
                </div>
              )}

              {isReassigning && (
                <div className="eco-row" style={{ background: '#f8fafc' }}>
                  <span style={{ gridColumn: 'span 7' }}>
                    <div
                      className="flex flex-wrap gap-4 items-end"
                      style={{
                        padding: 12,
                        border: '1px solid #d9e3f0',
                        borderRadius: 12,
                        background: '#fff',
                      }}
                    >
                      <div>
                        <label className="block text-xs text-slate-600">Inspector</label>
                        <select
                          className="auth-input"
                          value={selectedInspector}
                          onChange={e => setSelectedInspector(e.target.value)}
                        >
                          <option value="">Select inspector</option>
                          {inspectors.map(i => (
                            <option key={i.id} value={i.id}>
                              {i.name} (#{i.id})
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="flex gap-2">
                        <button
                          className="btn-eco sm"
                          disabled={busyId === a.id || !selectedInspector}
                          onClick={async () => {
                            if (!selectedInspector) return;
                            setBusyId(a.id);
                            try {
                              await reassign(a.id, { inspector_id: Number(selectedInspector) });
                              await load();
                              setReassignApptId(null);
                            } finally {
                              setBusyId(null);
                            }
                          }}
                        >
                          {busyId === a.id ? 'Saving...' : 'Save'}
                        </button>
                        <button className="btn-outline sm" onClick={() => setReassignApptId(null)}>
                          Cancel
                        </button>
                      </div>
                    </div>
                  </span>
                </div>
              )}
            </React.Fragment>
          );
        })}
        {rows.length === 0 && (
          <div className="p-6 text-center text-slate-500">No appointments this week.</div>
        )}
      </div>
    </div>
  );
}
