import React from 'react'

const RiskChip: React.FC<{ label: string; color?: string }> = ({ label, color }) => {
  return (
    <span className="role-chip" style={{ background: 'var(--surface)', borderColor: 'var(--border)', color: '#111', display: 'inline-flex', alignItems: 'center' }}>
      <span style={{ width: 8, height: 8, background: color || 'var(--success)', borderRadius: 999, marginRight: 6 }} />
      {label}
    </span>
  )
}

export default RiskChip

