import React, { useCallback, useEffect, useState } from 'react';
import {
  addFeedbackLabel,
  listFeedbackLogs,
  FeedbackLogItem,
  FeedbackLabelIn,
} from '../api/feedback';
import { updateCaseStatus } from '../api/cases';

type FeedbackPanelProps = {
  embeddedCaseId?: number;
  showLogs?: boolean;
  onConfirmed?: () => Promise<void> | void;
  isClosed?: boolean;
};

const FeedbackPanel: React.FC<FeedbackPanelProps> = ({
  embeddedCaseId,
  showLogs = true,
  onConfirmed,
  isClosed = false,
}) => {
  const isEmbedded = embeddedCaseId !== undefined;
  const labelOptions: { value: 'fraud' | 'non_fraud' | 'uncertain'; text: string }[] = [
    { value: 'fraud', text: 'Fraud' },
    { value: 'non_fraud', text: 'No Fraud' },
    { value: 'uncertain', text: 'Uncertain' },
  ];
  // form state
  const [caseId, setCaseId] = useState<number | ''>(embeddedCaseId ?? '');
  const [label, setLabel] = useState<'fraud' | 'non_fraud' | 'uncertain'>('fraud');
  const [source, setSource] = useState<string>('manager_ui');
  const [notes, setNotes] = useState<string>('');

  // logs state
  const [from, setFrom] = useState<string>(''); // YYYY-MM-DD
  const [to, setTo] = useState<string>('');     // YYYY-MM-DD
  const [logs, setLogs] = useState<FeedbackLogItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [posting, setPosting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [confirmMessage, setConfirmMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const data = await listFeedbackLogs({
        from: from || undefined,
        to: to || undefined,
      });
      setLogs(data);
    } catch (e: any) {
      setError(e.message || 'Failed to load logs');
    } finally {
      setLoading(false);
    }
  }, [from, to]);

  useEffect(() => {
    if (embeddedCaseId !== undefined) {
      setCaseId(embeddedCaseId);
    }
  }, [embeddedCaseId]);

  useEffect(() => {
    if (showLogs) {
      load();
    }
  }, [load, showLogs]); // first load + refilter

  const performSubmit = async (targetCaseId: number, chosenLabel: typeof label, customNotes?: string) => {
    setPosting(true); setError(null);
    try {
      const payload: FeedbackLabelIn = {
        case_id: targetCaseId,
        label: chosenLabel,
        source,
        notes: customNotes || undefined,
      };
      await addFeedbackLabel(payload);
      // Refresh table
      if (showLogs) await load();
    } catch (e: any) {
      setError(e.message || 'Failed to submit feedback');
    } finally {
      setPosting(false);
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (caseId === '') return;
    await performSubmit(Number(caseId), label, notes || undefined);
    setNotes('');
  };

  const handleEmbeddedSelect = async (value: typeof label) => {
    setLabel(value);
    if (!embeddedCaseId) return;
    await performSubmit(embeddedCaseId, value);
  };

  const handleConfirm = async () => {
    if (!embeddedCaseId) return;
    setConfirming(true);
    setConfirmMessage(null);
    try {
      await updateCaseStatus(embeddedCaseId, 'Closed');
      setConfirmMessage({ type: 'success', text: 'Case marked as Closed.' });
      if (onConfirmed) {
        await onConfirmed();
      }
    } catch (e: any) {
      setConfirmMessage({ type: 'error', text: e?.message || 'Failed to confirm status.' });
    } finally {
      setConfirming(false);
    }
  };

  const handleRefresh = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    load();
  };

  if (isEmbedded) {
    return (
      <div className="eco-card">
        <div className="eco-card-head">
          <h3>Feedback</h3>
        </div>
        <label style={{ fontWeight: 600, display: 'block', marginBottom: 6 }}>Label</label>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {labelOptions.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => handleEmbeddedSelect(opt.value)}
              disabled={posting || isClosed}
              style={{
                flex: '1 1 120px',
                padding: '10px 14px',
                borderRadius: 999,
                border: `1px solid ${
                  label === opt.value ? 'rgba(27,94,32,0.8)' : 'rgba(27,94,32,0.3)'
                }`,
                background:
                  label === opt.value ? 'rgba(27,94,32,0.15)' : 'rgba(27,94,32,0.05)',
                color: label === opt.value ? '#1b5e20' : '#2e7d32',
                fontWeight: 600,
                cursor: posting ? 'not-allowed' : 'pointer',
                transition: 'all 0.2s ease',
              }}
            >
              {opt.text}
            </button>
          ))}
        </div>
        <div
          style={{
            marginTop: 20,
            padding: '12px 16px',
            background: '#fff',
            borderRadius: 12,
            border: '1px solid rgba(27, 94, 32, 0.2)',
            textAlign: 'center',
          }}
        >
          <span style={{ fontSize: '1.2rem', fontWeight: 600, display: 'block' }}>Result</span>
          <span
            style={{
              fontSize: '1.8rem',
              fontWeight: 800,
              color: label === 'fraud' ? '#c62828' : '#1b5e20',
              textTransform: 'capitalize',
            }}
          >
            {label === 'non_fraud' ? 'No Fraud' : label}
          </span>
        </div>
        <button
          className="btn-eco"
          style={{ marginTop: 16 }}
          type="button"
          onClick={handleConfirm}
          disabled={confirming || isClosed}
        >
          {confirming ? 'Confirming…' : 'Confirm'}
        </button>
        {confirmMessage && (
          <div
            className={confirmMessage.type === 'success' ? 'eco-success' : 'eco-error'}
            style={{ marginTop: 8 }}
          >
            {confirmMessage.text}
          </div>
        )}
        {error && <div className="eco-error" style={{ marginTop: 12 }}>{error}</div>}
      </div>
    );
  }

  return (
    <div className="eco-card">
      <div className="eco-card-head">
        <h3>Feedback</h3>
      </div>

      {/* Add label form */}
      <form onSubmit={submit} className="eco-grid two" style={{ alignItems: 'end' }}>
        <div>
          <label>Case ID</label>
          <input
            type="number"
            value={caseId}
            onChange={e => setCaseId(e.target.value === '' ? '' : Number(e.target.value))}
            placeholder="e.g. 12"
          />
        </div>
        <div>
          <label>Label</label>
          <select value={label} onChange={e => setLabel(e.target.value as any)}>
            <option value="fraud">fraud</option>
            <option value="non_fraud">non_fraud</option>
            <option value="uncertain">uncertain</option>
          </select>
        </div>
        <div>
          <label>Source</label>
          <input value={source} onChange={e => setSource(e.target.value)} />
        </div>
        <div className="col-span-2">
          <label>Notes</label>
          <textarea
            rows={3}
            value={notes}
            onChange={e => setNotes(e.target.value)}
            placeholder="Optional notes…"
          />
        </div>
        <div>
          <button className="btn-eco" disabled={posting || caseId === ''}>
            {posting ? 'Saving…' : 'Add Label'}
          </button>
        </div>
      </form>

      {showLogs && (
        <>
          {/* Filters */}
          <div className="eco-grid two" style={{ marginTop: 16 }}>
            <div>
              <label>From</label>
              <input type="date" value={from} onChange={e => setFrom(e.target.value)} />
            </div>
            <div>
              <label>To</label>
              <input type="date" value={to} onChange={e => setTo(e.target.value)} />
            </div>
            <div>
              <button
                type="button"
                className="btn-outline"
                onClick={handleRefresh}
                disabled={loading}
              >
                {loading ? 'Loading…' : 'Refresh Logs'}
              </button>
            </div>
          </div>

          {error && <div className="eco-error">{error}</div>}

          {/* Logs table */}
          <div className="eco-table compact" style={{ marginTop: 16 }}>
            <div className="eco-thead">
              <span>Time</span>
              <span>Case</span>
              <span>Label</span>
              <span>Source</span>
              <span>Notes</span>
            </div>
            {logs.map(r => (
              <div className="eco-row" key={r.id}>
                <span>{new Date(r.created_at).toLocaleString()}</span>
                <span>{r.case_id}</span>
                <span>{r.label}</span>
                <span>{r.source || '—'}</span>
                <span>{r.notes || '—'}</span>
              </div>
            ))}
            {(!loading && logs.length === 0) && (
              <div className="eco-row"><span>No feedback yet.</span></div>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default FeedbackPanel;
