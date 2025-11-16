import React, { useState } from "react";

const TrackTicket: React.FC = () => {
  const [ticketId, setTicketId] = useState("");
  const [ticket, setTicket] = useState<any>(null);
  const [note, setNote] = useState("");
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const handleSearch = async () => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/tickets/${ticketId}`);
      const data = await res.json();

      if (res.ok) {
        setTicket(data);
        setMessage(null);
      } else {
        const detail = data?.detail || data?.message || "Ticket not found.";
        setMessage({ type: "error", text: `❌ ${detail}` });
      }
    } catch (err) {
      setMessage({ type: "error", text: `❌ Network error: ${err}` });
    }
  };

  const handleFollowUp = async () => {
    try {
      const formData = new FormData();
      formData.append("note", note);

      const res = await fetch(`http://127.0.0.1:8000/tickets/${ticketId}/followup`, {
        method: "POST",
        body: formData,
      });

      const data = await res.json().catch(() => null);

      if (!res.ok) {
        const detail =
          (typeof data === "string"
            ? data
            : data?.detail || data?.message || JSON.stringify(data)) ||
          `Error while adding follow-up (code ${res.status}).`;
        throw new Error(detail);
      }

      setMessage({ type: "success", text: "Follow-up added successfully!" });
      setNote("");
    } catch (err: any) {
      const errMsg =
        typeof err.message === "object"
          ? JSON.stringify(err.message)
          : err.message;
      setMessage({ type: "error", text: `${errMsg}` });
    }
  };

  return (
    <div className="ms-home">
      <section className="auth-wrapper">
        <div className="auth-card">
          <h2 className="auth-title">Track Ticket</h2>
          <p className="auth-sub">
            Enter your Ticket ID to view status or add a follow-up.
          </p>

          <div className="auth-field">
            <label className="auth-label">Ticket ID</label>
            <input
              className="auth-input"
              value={ticketId}
              onChange={(e) => setTicketId(e.target.value)}
              required
            />
            <button
              className="btn-primary"
              style={{ marginTop: 10 }}
              onClick={handleSearch}
            >
              Track
            </button>
          </div>

          {ticket && (
            <>
              <hr style={{ margin: "1rem 0" }} />
              <p>
                <strong>Status:</strong> {ticket.status}
              </p>
              <p>
                <strong>Subject:</strong> {ticket.subject}
              </p>
              <p>
                <strong>Description:</strong> {ticket.description}
              </p>

              <div className="auth-field" style={{ marginTop: "1rem" }}>
                <label className="auth-label">Add Follow-up Note</label>
                <textarea
                  className="auth-input"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                />
                <button className="btn-outline" onClick={handleFollowUp}>
                  Add Follow-up
                </button>
              </div>
            </>
          )}

          {message && (
            <p
              className={
                message.type === "success"
                  ? "helper-success"
                  : "helper-error"
              }
            >
              {message.text}
            </p>
          )}
        </div>
      </section>
    </div>
  );
};

export default TrackTicket;
