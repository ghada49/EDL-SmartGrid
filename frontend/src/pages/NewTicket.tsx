import React, { useState } from "react";

const NewTicket: React.FC = () => {
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const formData = new FormData();
    formData.append("subject", subject);
    formData.append("description", description);
    if (file) formData.append("file", file);

    try {
      const res = await fetch("http://127.0.0.1:8000/tickets/", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();

      if (res.ok) {
        setMessage(`Ticket submitted! ID: ${data.ticket_id}`);
        setSubject("");
        setDescription("");
        setFile(null);
      } else {
        const detail =
          (data && (data.detail || data.message)) ||
          `Unexpected error (code ${res.status})`;
        setMessage(`Error: ${detail}`);
      }
    } catch (err) {
      setMessage(`Network error: ${err}`);
    }
  };

  return (
    <div className="ms-home">
      <section className="auth-wrapper">
        <div className="auth-card">
          <h2 className="auth-title">Report an Issue</h2>
          <p className="auth-sub">
            Submit a new complaint or report a problem.
          </p>
          <form onSubmit={handleSubmit} encType="multipart/form-data">
            <div className="auth-field">
              <label className="auth-label">Subject</label>
              <input
                className="auth-input"
                name="subject"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                required
              />
            </div>

            <div className="auth-field">
              <label className="auth-label">Description</label>
              <textarea
                className="auth-input"
                name="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={4}
              />
            </div>

            <div className="auth-field">
              <label className="auth-label">Attach Evidence (optional)</label>
              <input
                type="file"
                className="auth-input"
                name="file"
                accept="image/*,application/pdf"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
            </div>

            <button className="btn-primary" type="submit">
              Submit Ticket
            </button>
            {message && <p className="helper-error">{message}</p>}
          </form>
        </div>
      </section>
    </div>
  );
};

export default NewTicket;
