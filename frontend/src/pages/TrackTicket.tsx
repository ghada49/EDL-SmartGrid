import React, { useEffect, useState } from "react";

type Ticket = {
  id: number;
  subject: string;
  status: string;
  description: string;
  photo_path?: string | null;
  created_at?: string;
};

const splitDescription = (description: string | null | undefined) => {
  if (!description) return { summary: "", followups: [] as string[] };

  const parts = description.split(/\n\n(?=\[Follow-up )/);
  const summary = parts.shift() ?? "";
  return { summary, followups: parts };
};

const redactFollowupForCitizen = (fu: string) => {
  const match = fu.match(/^\[Follow-up (.+?) [–-] ([^\]]+)\]:\s*(.*)$/);
  if (!match) return fu;
  const [, meta, actor, body] = match;
  const actorLabel = actor.includes("@") ? "Manager" : actor;
  return `[Follow-up ${meta} – ${actorLabel}]: ${body}`;
};

const API_BASE = "http://127.0.0.1:8000";

const TrackTicket: React.FC = () => {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const token = localStorage.getItem("token");

  // --------------------------------------------
  // Load all citizen tickets automatically
  // --------------------------------------------
  const loadTickets = async () => {
    try {
      const res = await fetch(`${API_BASE}/tickets/mine`, {
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
    const note = notes[ticketId]?.trim();
    if (!note) {
      setMessage({ type: "error", text: "Enter a follow-up note before submitting." });
      return;
    }

    try {
      const formData = new FormData();
      formData.append("note", note);

      const res = await fetch(`${API_BASE}/tickets/${ticketId}/followup`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed");

      setMessage({ type: "success", text: "Follow-up added!" });
      setNotes((prev) => ({ ...prev, [ticketId]: "" }));
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

          {tickets.map((t) => {
            const { summary, followups } = splitDescription(t.description);

            return (
              <div
                key={t.id}
                className="eco-card"
                style={{ padding: 16, marginTop: 14 }}
              >
                <strong>#{t.id} — {t.subject}</strong>
                <p>Status: {t.status}</p>
                {t.created_at && (
                  <p className="eco-muted">
                    Created: {new Date(t.created_at).toLocaleString()}
                  </p>
                )}

                <div style={{ marginTop: 12 }}>
                  <h4 style={{ margin: "0 0 4px" }}>Description</h4>
                  <pre className="eco-pre" style={{ whiteSpace: "pre-wrap" }}>
                    {summary || "No description provided."}
                  </pre>
                </div>

                {followups.length > 0 && (
                  <div style={{ marginTop: 10 }}>
                    <h4 style={{ margin: "0 0 4px" }}>Follow-ups</h4>
                    <ol className="eco-steps">
                      {followups.map((fu, idx) => (
                        <li key={idx} style={{ whiteSpace: "pre-wrap" }}>
                          {redactFollowupForCitizen(fu)}
                        </li>
                      ))}
                    </ol>
                  </div>
                )}

                {t.photo_path && (
                  <div style={{ marginTop: 12 }}>
                    <h4 style={{ margin: "0 0 4px" }}>Evidence</h4>
                    <img
                      src={`${API_BASE}/${t.photo_path}`}
                      alt="ticket evidence"
                      style={{ width: "100%", maxWidth: 360, borderRadius: 8 }}
                    />
                  </div>
                )}

                <div style={{ marginTop: 14 }}>
                  <textarea
                    className="auth-input"
                    placeholder="Add follow-up note"
                    value={notes[t.id] ?? ""}
                    onChange={(e) =>
                      setNotes((prev) => ({ ...prev, [t.id]: e.target.value }))
                    }
                  />
                  <button
                    className="btn-outline"
                    style={{ marginTop: 8 }}
                    onClick={() => handleFollowUp(t.id)}
                  >
                    Add Follow-up
                  </button>
                </div>
              </div>
            );
          })}

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
