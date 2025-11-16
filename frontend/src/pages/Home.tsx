import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { FaMapMarkerAlt, FaClipboardList, FaBolt } from 'react-icons/fa'

const Home: React.FC = () => {
  const nav = useNavigate();

  return (
    <div className="ms-home">

      <section className="ms-hero">
        <h1>
          Smart Energy Transparency
          <br />
          For Beirut
        </h1>
        <p>
          Sign up or log in to discover data-driven insights, report anomalies, and help improve municipal energy fairness.
        </p>

        <div className="ms-hero__buttons">
          <button className="ms-btn ms-btn--primary" onClick={() => nav("/signup")}>
            Sign Up
          </button>
          <button className="ms-btn ms-btn--ghost" onClick={() => nav("/login")}>
            Log In
          </button>
        </div>
      </section>

      <section className="ms-cards">
        <div className="ms-card">
          <div className="ms-card__icon" aria-hidden><FaMapMarkerAlt /></div>
          <h3>Report an Issue</h3>
          <p>Submit a complaint or report a problem online</p>
          <Link to="/signup" className="ms-card__link">Start</Link>
        </div>

        <div className="ms-card">
          <div className="ms-card__icon" aria-hidden><FaClipboardList /></div>
          <h3>Track My Ticket</h3>
          <p>Check the status of your submitted issues.</p>
          <Link to="/signup" className="ms-card__link">Track</Link>
        </div>

        <div className="ms-card">
          <div className="ms-card__icon" aria-hidden><FaBolt /></div>
          <h3>Expected kWh Tool</h3>
          <p>Estimate your household’s electricity consumption</p>
          <Link to="/signup" className="ms-card__link">Open</Link>
        </div>
      </section>
    </div>
  );
};

export default Home;
