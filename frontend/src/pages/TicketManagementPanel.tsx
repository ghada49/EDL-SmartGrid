import React, { useEffect, useMemo, useState } from "react";
import {
  listTickets,
  getTicket,
  updateTicketStatus,
  addTicketFollowup,
  TicketRow as Ticket,
} from "../api/tickets";
import { API_BASE_URL } from "../api/client";

const TicketManagementPanel: React.FC = () => {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState<any | null>(null);
  const [detailId, setDetailId] = useState<number | null>(null);
  const [followNote, setFollowNote] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");

  const loadTickets = async () => {
    setLoading(true);
    try {
      const data = await listTickets();
      setTickets(data);
    } catch (err) {
      console.error("Failed to load tickets:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTickets();
  }, []);

  const displayTickets = statusFilter
    ? tickets.filter((ticket) => ticket.status === statusFilter)
    : tickets;

  const evidenceUrl = useMemo(() => {
    if (!detail?.photo_path) return null;
    const clean = detail.photo_path.replace(/^\/+/, "").replace(/\\/g, "/");
    // Use the same API base URL as other authenticated calls to fetch the static file.
    return `${API_BASE_URL}/${clean}`;
  }, [detail]);

  return (
    <div className="eco-card">
      <div className="eco-card-head">
        <h3>Ticket Management Panel</h3>
      </div>

      <div className="eco-row" style={{ marginBottom: 16 }}>
        <label style={{ fontWeight: 600 }}>Filter by status</label>
        <select
          className="auth-input"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">All statuses</option>
          <option value="New">New</option>
          <option value="In Review">In Review</option>
          <option value="Closed">Closed</option>
        </select>
      </div>

      {loading && <p>Loading...</p>}

      {!loading && displayTickets.length === 0 && (
        <p>No tickets match the selected status.</p>
      )}

      {displayTickets.map((t) => (
        <div className="eco-row" key={t.id}>
          <span>Ticket #{t.id}</span>
          <span>Status: {t.status}</span>
          <span>User: {t.user_name ?? t.user_email ?? t.user_id}</span>

          <div className="eco-actions">
            {/* View Ticket */}
            <button
              className="btn-outline sm"
              onClick={async () => {
                try {
                  setDetailId(t.id);
                  const info = await getTicket(t.id);
                  setDetail(info);
                } catch (err) {
                  console.error(err);
                }
              }}
            >
              View
            </button>

            {/* Change Status */}
            <select
              className="auth-input"
              defaultValue=""
              onChange={async (e) => {
                const v = e.target.value;
                if (!v) return;

                try {
                  await updateTicketStatus(t.id, v);
                  await loadTickets();
                } catch (err) {
                  console.error(err);
                }

                e.currentTarget.value = "";
              }}
            >
              <option value="" disabled>
                Change Status
              </option>
              <option value="In Review">In Review</option>
              <option value="Closed">Closed</option>
            </select>
          </div>
        </div>
      ))}

      {/* Ticket Detail Modal */}
      {detailId && detail && (
        <div className="eco-modal">
          <div className="eco-modal-content">
            <button
              className="eco-modal-close"
              aria-label="Close ticket details"
              onClick={() => {
                setDetailId(null);
                setDetail(null);
              }}
            >
              &times;
            </button>
            <h3>Ticket #{detailId}</h3>
            <p>Status: {detail.status}</p>
            <p>Subject: {detail.subject}</p>
            <p>Description:</p>
            <pre className="eco-pre">{detail.description}</pre>

            {evidenceUrl && (
              <img
                src={evidenceUrl}
                alt="ticket evidence"
                style={{ width: "100%", marginTop: 8 }}
              />
            )}

            {/* Follow-up */}
            <div className="eco-actions" style={{ marginTop: 12 }}>
              <textarea
                className="auth-input"
                placeholder="Add follow-up note"
                value={followNote}
                onChange={(e) => setFollowNote(e.target.value)}
              ></textarea>

              <button
                className="btn-outline sm"
                onClick={async () => {
                  if (!followNote) return;

                  try {
                    await addTicketFollowup(detailId, followNote);
                    const refreshed = await getTicket(detailId);
                    setDetail(refreshed);
                    setFollowNote("");
                  } catch (err) {
                    console.error(err);
                  }
                }}
              >
                Add Follow-Up
              </button>
            </div>

          </div>
        </div>
      )}
    </div>
  );
};

export default TicketManagementPanel;
