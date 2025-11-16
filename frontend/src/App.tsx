import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import TopNav from "./components/TopNav";
import Home from "./pages/Home";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import CitizenPortal from "./pages/CitizenPortal";
import InspectorRoutes from "./pages/InspectorRoutes";
import ManagerDashboard from "./pages/ManagerDashboard";
import MapView from "./pages/MapView";
import ProtectedRoute from "./routes/ProtectedRoute";
import AdminDashboard from "./pages/AdminDashboard";
// 🆕 Citizen ticket pages
import NewTicket from "./pages/NewTicket";
import TrackTicket from "./pages/TrackTicket";

const App: React.FC = () => {
  return (
    <div className="layout">
      <TopNav />

      <main className="content">
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

          {/* Inspector view */}
          <Route
            path="/inspector"
            element={
              <ProtectedRoute roles={["Inspector"]}>
                <InspectorRoutes />
              </ProtectedRoute>
            }
          />

          {/* Manager / Admin views */}
          <Route
            path="/manager"
            element={
              <ProtectedRoute roles={["Manager"]}>
                <ManagerDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin"
            element={
              <ProtectedRoute roles={["Admin"]}>
                <AdminDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/map"
            element={
              <ProtectedRoute roles={["Manager"]}>
                <MapView />
              </ProtectedRoute>
            }
          />

          {/* Fallback redirect */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
};

export default App;
