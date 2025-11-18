import React, { useEffect, useState } from "react";

const TrackTicket: React.FC = () => {
  const [tickets, setTickets] = useState<any[]>([]);
  const [selected, setSelected] = useState<any | null>(null);
  const [note, setNote] = useState("");
  const [message, setMessage] = useState<any>(null);

  const token = localStorage.getItem("token");

  // --------------------------------------------
  // Load all citizen tickets automatically
  // --------------------------------------------
  const loadTickets = async () => {
    try {
      const res = await fetch("http://127.0.0.1:8000/tickets/mine", {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      const data = await res.json();
      if (res.ok) setTickets(data);
      else setMessage({ type: "error", text: data.detail || "Error loading tickets" });
    } catch (err) {
      setMessage({ type: "error", text: "Network error loading tickets" });
    }
  };

  useEffect(() => {
    loadTickets();
  }, []);

  // --------------------------------------------
  // Add follow-up
  // --------------------------------------------
  const handleFollowUp = async (ticketId: number) => {
    try {
      const formData = new FormData();
      formData.append("note", note);

      const res = await fetch(
        `http://127.0.0.1:8000/tickets/${ticketId}/followup`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        }
      );

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed");

      setMessage({ type: "success", text: "Follow-up added!" });
      setNote("");
      loadTickets();
    } catch (err: any) {
      setMessage({ type: "error", text: err.message });
    }
  };

  return (
    <div className="ms-home">
      <section className="auth-wrapper">
        <div className="auth-card">

          <h2 className="auth-title">My Tickets</h2>
          <p className="auth-sub">View the tickets you submitted.</p>

          {/* ---------------- Ticket List ---------------- */}
          {tickets.length === 0 && (
            <p className="helper-error">You have no submitted tickets.</p>
          )}

          {tickets.map((t) => (
            <div
              key={t.id}
              className="eco-card"
              style={{ padding: 12, marginTop: 14, cursor: "pointer" }}
              onClick={() => setSelected(t)}
            >
              <strong>#{t.id} — {t.subject}</strong>
              <p>Status: {t.status}</p>
            </div>
          ))}

          {/* ---------------- Ticket Detail Modal ---------------- */}
          {selected && (
            <div className="eco-modal">
              <div className="eco-modal-content">
                <h3>Ticket #{selected.id}</h3>

                <p><strong>Status:</strong> {selected.status}</p>
                <p><strong>Description:</strong> {selected.description}</p>

                {selected.photo_path && (
                  <img
                    src={`http://127.0.0.1:8000/${selected.photo_path}`}
                    alt="evidence"
                    style={{ width: "100%", maxWidth: 300, marginTop: 10 }}
                  />
                )}

                <textarea
                  className="auth-input"
                  placeholder="Add follow-up note"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                />

                <button
                  className="btn-outline"
                  onClick={() => handleFollowUp(selected.id)}
                >
                  Add Follow-up
                </button>

                <button
                  className="btn-primary"
                  onClick={() => setSelected(null)}
                >
                  Close
                </button>
              </div>
            </div>
          )}

          {message && (
            <p
              className={
                message.type === "success" ? "helper-success" : "helper-error"
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
