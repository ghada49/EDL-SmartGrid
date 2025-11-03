import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import LeftNav from './components/LeftNav'
import Home from './pages/Home'
import Login from './pages/Login'
import Signup from './pages/Signup'
import CitizenPortal from './pages/CitizenPortal'
import InspectorRoutes from './pages/InspectorRoutes'
import ManagerDashboard from './pages/ManagerDashboard'
import MapView from './pages/MapView'
import ProtectedRoute from './routes/ProtectedRoute'
import TopNav from './components/TopNav'

const App: React.FC = () => {
  const hideLeftNav = location.pathname === "/"; // hide left nav on public home

  return (
    <div className="layout">
      {/* Remove your old TopBar/LeftNav for the public home */}
      {!hideLeftNav && <LeftNav />}

      <main className={`content ${hideLeftNav ? "content--full" : ""}`}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/" element={<Home />} />

          <Route path="/citizen" element={<ProtectedRoute roles={["Citizen"]}><CitizenPortal /></ProtectedRoute>} />
          <Route path="/inspector" element={<ProtectedRoute roles={["Inspector"]}><InspectorRoutes /></ProtectedRoute>} />
          <Route path="/manager" element={<ProtectedRoute roles={["Manager","Admin"]}><ManagerDashboard /></ProtectedRoute>} />
          <Route path="/map" element={<ProtectedRoute roles={["Manager","Admin"]}><MapView /></ProtectedRoute>} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}
export default App
