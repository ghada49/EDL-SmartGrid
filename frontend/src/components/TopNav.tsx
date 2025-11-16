import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const TopNav: React.FC = () => {
  const { role, signOut } = useAuth();
  const nav = useNavigate();

  const dashboardPath =
    role === "Citizen" ? "/citizen" :
    role === "Inspector" ? "/inspector" :
    role === "Manager" ? "/manager" :
    role === "Admin" ? "/admin" :
    "/";

  return (
    <header className="ms-nav">
      <div className="ms-nav__brand" style={{ cursor: "pointer" }}>
        <span className="ms-dot" />
        <span>EDL SmartGrid Portal</span>
      </div>

      <nav className="ms-nav__links">
        {/* Always show Home */}
        

        {/* If not logged in */}
        {!role && (
          <>
            <Link to="/">Home</Link>
            <Link to="/login" className="ms-chip">Log In</Link>
            <Link to="/signup" className="ms-chip">Sign Up</Link>
          </>
        )}

        {/* If logged in */}
        {role && (
          <>
            <span className="ms-chip" title="Your role">{role}</span>
            <Link to={dashboardPath}>Dashboard</Link>
            <button
              className="ms-chip"
              onClick={signOut}
              style={{ background: "transparent", cursor: "pointer" }}
            >
              Logout
            </button>
          </>
        )}
      </nav>
    </header>
  );
};

export default TopNav;