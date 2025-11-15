// src/components/StatusBadge.tsx
export default function StatusBadge({ status }: { status: string }) {
  const cls = {
    pending: 'bg-yellow-100 text-yellow-800',
    accepted: 'bg-emerald-100 text-emerald-800',
    closed: 'bg-slate-200 text-slate-700',
  }[status] || 'bg-slate-100 text-slate-700';
  return <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}>{status}</span>;
}
