import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import {
  FaMapMarkerAlt,
  FaClipboardList,
  FaBolt,
  FaExclamationTriangle,
  FaShieldAlt,
  FaInfoCircle,
  FaLightbulb,
  FaArrowRight,
  FaChevronDown,
} from "react-icons/fa";

type IconType = "warning" | "shield" | "info" | "tip";

const CitizenPortal: React.FC = () => {
  const [openFaq, setOpenFaq] = useState<number | null>(0);
  const [showFaqModal, setShowFaqModal] = useState(false);

  const faqs: {
    question: string;
    answer: string;
    type: IconType;
  }[] = [
    {
      question: "How can I identify suspicious electricity consumption?",
      answer:
        "Watch for sudden, unexplained spikes in your bill, unusually high consumption compared to similar households, or meter readings that don't match your actual usage. If your bill increases significantly without changes in your lifestyle, it's worth investigating.",
      type: "warning",
    },
    {
      question: "What are common signs of electricity meter tampering?",
      answer:
        "Look for physical damage to the meter, broken seals, unusual wiring around the meter box, the meter running backwards, or the meter stopping completely while appliances are on. If you notice any of these, report it immediately.",
      type: "shield",
    },
    {
      question: "What are illegal connections and how do I spot them?",
      answer:
        "Illegal connections include unauthorized wires bypassing the meter, jumper cables connecting directly to power lines, or connections running from one property to another. Look for exposed wires, unusual cables running to neighbors, or power usage without a visible meter connection.",
      type: "warning",
    },
    {
      question: "How does electricity fraud affect my community?",
      answer:
        "Electricity theft increases costs for honest consumers, overloads the power grid causing outages, poses serious fire and safety hazards, and diverts resources from infrastructure improvements. Reporting fraud helps keep electricity affordable and reliable for everyone.",
      type: "info",
    },
    {
      question: "What should I do if I suspect my neighbor is stealing electricity?",
      answer:
        "Report it confidentially through our platform. Never confront them directly or attempt to investigate yourself, as this can be dangerous. Our team will handle the investigation professionally and discretely.",
      type: "shield",
    },
    {
      question: "What are the penalties for electricity theft?",
      answer:
        "Penalties vary but typically include hefty fines, back-payment of stolen electricity, disconnection of service, and potential criminal charges. In serious cases, offenders may face imprisonment. The legal and financial consequences far outweigh any short-term savings.",
      type: "warning",
    },
    {
      question: "How can I reduce my electricity bill legitimately?",
      answer:
        "Use energy-efficient LED bulbs, unplug devices when not in use, maintain your appliances regularly, use natural light when possible, and avoid running high-consumption appliances during peak hours. Small changes can make a big difference!",
      type: "tip",
    },
    {
      question: "Is it illegal to share electricity with my neighbor?",
      answer:
        "Yes, sharing your electricity connection with neighbors is illegal and dangerous. It overloads circuits, creates fire hazards, makes accurate billing impossible, and you could be held liable for their consumption. Each property must have its own authorized connection.",
      type: "warning",
    },
    {
      question: "What happens after I submit a fraud report?",
      answer:
        "Our team reviews your report within 24-48 hours, conducts an investigation if warranted, and may perform on-site inspections. You'll receive updates on your ticket status. All reports are taken seriously and help us maintain system integrity for everyone.",
      type: "info",
    },
    {
      question: "Can I request a meter accuracy test if I suspect problems?",
      answer:
        "Yes. If you believe your meter is faulty, you can request an official accuracy test. A technician will check the device in controlled conditions. If an error is confirmed, the bill can be corrected according to the applicable rules.",
      type: "info",
    },
  ];

  const renderIcon = (type: IconType) => {
    switch (type) {
      case "warning":
        return <FaExclamationTriangle />;
      case "shield":
        return <FaShieldAlt />;
      case "info":
        return <FaInfoCircle />;
      case "tip":
      default:
        return <FaLightbulb />;
    }
  };

  // lock background scroll + ESC close
  useEffect(() => {
    if (!showFaqModal) return;
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setShowFaqModal(false);
    };
    window.addEventListener("keydown", onKeyDown);

    return () => {
      document.body.style.overflow = originalOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [showFaqModal]);

  return (
    <div className="ms-home">
      {/* Hero */}
      <section className="ms-hero">
        <h1>Citizen Portal</h1>
        <p>
          Report issues, track tickets, and learn how to detect and safely report
          electricity fraud.
        </p>
      </section>

      {/* Cards */}
      <section className="ms-cards ms-cards--center">
        {/* Report an Issue */}
        <div className="ms-card ms-card--center">
          <div className="ms-card__icon ms-card__icon--xl" aria-hidden>
            <FaMapMarkerAlt />
          </div>
          <h3>Report an Issue</h3>
          <p>Pin a location, add a description and (optional) photo.</p>
          <Link to="/tickets/new" className="ms-card__link">
            Start
          </Link>
        </div>

        {/* Track Ticket */}
        <div className="ms-card ms-card--center">
          <div className="ms-card__icon ms-card__icon--xl" aria-hidden>
            <FaClipboardList />
          </div>
          <h3>Track My Ticket</h3>
          <p>Follow status: New → In Review → Closed.</p>
          <Link to="/tickets/track" className="ms-card__link">
            Track
          </Link>
        </div>

        {/* Fraud Prevention Guide */}
        <div
          className="ms-card ms-card--center ms-card--clickable cp-card-accent"
          onClick={() => setShowFaqModal(true)}
        >
          <div className="ms-card__icon ms-card__icon--xl" aria-hidden>
            <FaBolt />
          </div>
          <h3>Fraud Prevention Guide</h3>
          <p>Clear answers about suspicious bills, tampering and safe reporting.</p>
          <button type="button" className="ms-card__link">
            Open Guide
          </button>
        </div>
      </section>

      {/* FAQ Modal */}
      {showFaqModal && (
        <div
          className="cp-modal-backdrop"
          onClick={() => setShowFaqModal(false)}
        >
          <div className="cp-modal" onClick={(e) => e.stopPropagation()}>
            {/* Header */}
            <header className="cp-modal__header">
              <div className="cp-modal__title-block">
                <div className="cp-modal__icon-circle">
                  <FaBolt />
                </div>
                <div>
                  <h2>Electricity Fraud Prevention</h2>
                  <p>Short, practical answers for everyday situations.</p>
                </div>
              </div>
              <button
                type="button"
                className="cp-modal__close"
                onClick={() => setShowFaqModal(false)}
                aria-label="Close"
              >
                ✕
              </button>
            </header>

            {/* Body */}
            <div className="cp-modal__body">
              <section className="cp-faq-list">
                {faqs.map((faq, index) => {
                  const isOpen = openFaq === index;
                  return (
                    <article
                      key={index}
                      className={`cp-faq-item cp-faq-item--${faq.type} ${
                        isOpen ? "cp-faq-item--open" : ""
                      }`}
                    >
                      <button
                        type="button"
                        className="cp-faq-item__header"
                        onClick={() =>
                          setOpenFaq(isOpen ? null : index)
                        }
                      >
                        <div className="cp-faq-item__left">
                          <div className={`cp-faq-item__icon cp-faq-item__icon--${faq.type}`}>
                            {renderIcon(faq.type)}
                          </div>
                          <h4>{faq.question}</h4>
                        </div>
                        <div
                          className={`cp-faq-item__chevron ${
                            isOpen ? "cp-faq-item__chevron--open" : ""
                          }`}
                        >
                          <FaChevronDown />
                        </div>
                      </button>

                      <div
                        className={`cp-faq-item__content ${
                          isOpen ? "cp-faq-item__content--open" : ""
                        }`}
                      >
                        <p>{faq.answer}</p>
                      </div>
                    </article>
                  );
                })}
              </section>

              {/* CTA */}
              <div className="cp-modal__cta">
                <div className="cp-modal__cta-text">
                  <h3>Spotted something suspicious?</h3>
                  <p>
                    Create a ticket with the exact location and a short description.
                    Our inspectors will handle the rest.
                  </p>
                </div>
                <Link
                  to="/tickets/new"
                  className="cp-modal__cta-button"
                  onClick={() => setShowFaqModal(false)}
                >
                  Report an Issue Now
                  <FaArrowRight className="cp-modal__cta-icon" />
                </Link>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Styles – simpler, single-column FAQ */}
      <style>{`
        .ms-card--clickable { cursor: pointer; }
        .cp-card-accent {
          position: relative;
          overflow: hidden;
        }
        .cp-card-accent::before {
          content: "";
          position: absolute;
          inset: -40%;
          background: radial-gradient(circle at top left, rgba(255, 255, 255, 0.25), transparent 60%);
          pointer-events: none;
        }

        .cp-modal-backdrop {
          position: fixed;
          inset: 0;
          background: rgba(15, 23, 42, 0.55);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          backdrop-filter: blur(3px);
        }

        .cp-modal {
          background: #f9fafb;
          max-width: 1200px;
          width: 96%;
          max-height: 95vh;
          border-radius: 24px;
          overflow: hidden;
          box-shadow: 0 32px 80px rgba(0, 0, 0, 0.35);
          display: flex;
          flex-direction: column;
        }

        .cp-modal__header {
          padding: 14px 22px;
          background: linear-gradient(120deg, #166534, #15803d, #22c55e);
          color: #ffffff;
          display: flex;
          align-items: center;
          justify-content: space-between;
        }

        .cp-modal__title-block {
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .cp-modal__icon-circle {
          width: 38px;
          height: 38px;
          border-radius: 999px;
          background: rgba(255, 255, 255, 0.16);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 1.1rem;
        }

        .cp-modal__header h2 {
          margin: 0;
          font-size: 1.1rem;
          font-weight: 700;
        }

        .cp-modal__header p {
          margin: 2px 0 0 0;
          font-size: 0.8rem;
          opacity: 0.9;
        }

        .cp-modal__close {
          border: none;
          background: transparent;
          color: #ffffff;
          font-size: 1.3rem;
          cursor: pointer;
        }

        .cp-modal__body {
          padding: 14px 18px 16px;
          overflow-y: auto;
        }

        .cp-faq-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
          margin-bottom: 14px;
        }

        .cp-faq-item {
          background: #ffffff;
          border-radius: 14px;
          border: 1px solid #e5e7eb;
          overflow: hidden;
          box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04);
          transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.1s ease;
          position: relative;
        }

        .cp-faq-item::before {
          content: "";
          position: absolute;
          left: 0;
          top: 0;
          bottom: 0;
          width: 3px;
          border-radius: 999px;
          background: #e5e7eb;
        }

        .cp-faq-item--warning::before { background: #fecaca; }
        .cp-faq-item--shield::before  { background: #bbf7d0; }
        .cp-faq-item--info::before    { background: #bfdbfe; }
        .cp-faq-item--tip::before     { background: #fde68a; }

        .cp-faq-item:hover {
          border-color: #a7f3d0;
          box-shadow: 0 10px 26px rgba(15, 23, 42, 0.12);
          transform: translateY(-1px);
        }

        .cp-faq-item__header {
          width: 100%;
          border: none;
          background: transparent;
          padding: 10px 14px 10px 18px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          cursor: pointer;
        }

        .cp-faq-item__left {
          display: flex;
          align-items: center;
          gap: 10px;
          text-align: left;
        }

        .cp-faq-item__icon {
          width: 28px;
          height: 28px;
          border-radius: 999px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 0.85rem;
        }
        .cp-faq-item__icon--warning {
          background: #fef2f2;
          color: #b91c1c;
        }
        .cp-faq-item__icon--shield {
          background: #ecfdf5;
          color: #15803d;
        }
        .cp-faq-item__icon--info {
          background: #eff6ff;
          color: #1d4ed8;
        }
        .cp-faq-item__icon--tip {
          background: #fffbeb;
          color: #b45309;
        }

        .cp-faq-item__header h4 {
          margin: 0;
          font-size: 0.92rem;
          color: #111827;
        }

        .cp-faq-item__chevron {
          display: inline-flex;
          transition: transform 0.2s ease;
          color: #6b7280;
        }
        .cp-faq-item__chevron--open {
          transform: rotate(180deg);
        }

        .cp-faq-item__content {
          max-height: 0;
          overflow: hidden;
          padding: 0 14px 0 18px;
          border-top: 1px solid transparent;
          transition: max-height 0.25s ease, padding 0.25s ease, border-color 0.25s ease;
          background: #f9fafb;
        }
        .cp-faq-item__content--open {
          max-height: 240px;
          padding: 8px 14px 11px 18px;
          border-color: #e5e7eb;
        }
        .cp-faq-item__content p {
          margin: 0;
          font-size: 0.85rem;
          color: #374151;
        }

        .cp-modal__cta {
          padding: 10px 14px 4px;
          border-top: 1px solid #e5e7eb;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 10px;
          flex-wrap: wrap;
        }

        .cp-modal__cta-text h3 {
          margin: 0 0 3px 0;
          font-size: 0.95rem;
          color: #111111;
        }
        .cp-modal__cta-text p {
          margin: 0;
          font-size: 0.8rem;
          color: #1a2028ff;
        }

        .cp-modal__cta-button {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 7px 14px;
          border-radius: 999px;
          background: #166534;
          color: #ffffff;
          font-size: 0.82rem;
          font-weight: 600;
          text-decoration: none;
          border: none;
          cursor: pointer;
          box-shadow: 0 8px 20px rgba(22, 101, 52, 0.35);
        }
        .cp-modal__cta-button:hover {
          background: #14532d;
        }
        .cp-modal__cta-icon {
          font-size: 0.8rem;
        }

        @media (max-width: 640px) {
          .cp-modal {
            max-width: 100%;
            border-radius: 0;
          }
        }
      `}</style>
    </div>
  );
};

export default CitizenPortal;

