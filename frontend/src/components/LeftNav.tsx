import React from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useTranslation } from 'react-i18next'
<Link to="/manager/scheduling" className="btn-link">Scheduling</Link>
const LeftNav: React.FC = () => {
  const { role } = useAuth()
  const { t } = useTranslation()

  return (
    <aside className="leftnav glass">
      <div className="brand">
        <div style={{ width:18, height:18, background:'var(--accent)', borderRadius:6 }} />
        <span>Municipality • Services</span>
      </div>

      <div className="nav">
        {!role && (
          <>
            <Link to="/">{t('home') || 'Home'}</Link>
            <Link to="/login">{t('login')}</Link>
            <Link to="/signup">{t('signup')}</Link>
          </>
        )}

        {role === 'Citizen' && (
          <>
            <Link to="/citizen">{t('citizenPortal')}</Link>
            <Link to="/tools/expected-kwh">Expected kWh Tool</Link>
            <Link to="/tickets/my">{t('myComplaints')}</Link>
          </>
        )}

        {role === 'Inspector' && (
          <>
            <Link to="/inspector">{t('todayRoutes')}</Link>
            <Link to="/cases">{t('cases')}</Link>
            <Link to="/reports">{t('reports')}</Link>
          </>
        )}

        {(role === 'Manager' || role === 'Admin') && (
          <>
            <Link to="/manager">{t('managerDashboard')}</Link>
            <Link to="/map">{t('map')}</Link>
            <Link to="/admin/users">Users</Link>
            <Link to="/admin/models">Models</Link>
            <Link to="/admin/datasets">Datasets</Link>
            <Link to="/admin/audit">Audit</Link>
          </>
        )}
      </div>
    </aside>
  )
}
export default LeftNav
