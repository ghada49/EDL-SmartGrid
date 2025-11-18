import React from "react";
import { Link } from "react-router-dom";
import { FaMapMarkerAlt, FaClipboardList, FaBolt } from "react-icons/fa";

const CitizenPortal: React.FC = () => {
  return (
    <div className="ms-home">

      {/* Optional small hero for context */}
      <section className="ms-hero">
        <h1>Citizen Portal</h1>
        <p>Report issues, track tickets, and estimate expected electricity usage.</p>
      </section>

      {/* Cards – centered & larger (uses your .ms-cards--center rules) */}
      <section className="ms-cards ms-cards--center">
        <div className="ms-card ms-card--center">
          <div className="ms-card__icon ms-card__icon--xl" aria-hidden>
            <FaMapMarkerAlt />
          </div>
          <h3>Report an Issue</h3>
          <p>Pin a location, add a description and (optional) photo.</p>
          <Link to="/tickets/new" className="ms-card__link">Start</Link>
        </div>

        <div className="ms-card ms-card--center">
          <div className="ms-card__icon ms-card__icon--xl" aria-hidden>
            <FaClipboardList />
          </div>
          <h3>Track My Ticket</h3>
          <p>Follow status: New → In Review → Closed.</p>
          <Link to="/tickets/track" className="ms-card__link">Track</Link>
        </div>

        <div className="ms-card ms-card--center">
          <div className="ms-card__icon ms-card__icon--xl" aria-hidden>
            <FaBolt />
          </div>
          <h3>Expected kWh Tool</h3>
          <p>Estimate usage by floors, apartments, and year.</p>
          <Link to="/tools/expected-kwh" className="ms-card__link">Open</Link>
        </div>
      </section>
    </div>
  );
};

export default CitizenPortal;
