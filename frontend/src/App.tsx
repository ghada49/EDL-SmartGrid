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

// 🆕 Import the two new Citizen pages
import NewTicket from './pages/NewTicket'
import TrackTicket from './pages/TrackTicket'

const App: React.FC = () => {
  const hideLeftNav = location.pathname === "/"; // hide left nav on public home

  return (
    <div className="layout">
      {/* Hide LeftNav only on the public home page */}
      {!hideLeftNav && <LeftNav />}

      <main className={`content ${hideLeftNav ? "content--full" : ""}`}>
        <Routes>
          {/* Public routes */}
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />

          {/* Citizen portal + ticket features */}
          <Route
            path="/citizen"
            element={
              <ProtectedRoute roles={["Citizen"]}>
                <CitizenPortal />
              </ProtectedRoute>
            }
          />
          <Route
            path="/tickets/new"
            element={
              <ProtectedRoute roles={["Citizen"]}>
                <NewTicket />
              </ProtectedRoute>
            }
          />
          <Route
            path="/tickets/track"
            element={
              <ProtectedRoute roles={["Citizen"]}>
                <TrackTicket />
              </ProtectedRoute>
            }
          />

          {/* Inspector and Manager views */}
          <Route
            path="/inspector"
            element={
              <ProtectedRoute roles={["Inspector"]}>
                <InspectorRoutes />
              </ProtectedRoute>
            }
          />
          <Route
            path="/manager"
            element={
              <ProtectedRoute roles={["Manager", "Admin"]}>
                <ManagerDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/map"
            element={
              <ProtectedRoute roles={["Manager", "Admin"]}>
                <MapView />
              </ProtectedRoute>
            }
          />

          {/* Fallback redirect */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
