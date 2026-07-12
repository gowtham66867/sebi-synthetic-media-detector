import { useState } from "react";
import type { IssueResponse } from "./types";

const API_BASE = import.meta.env.DEV ? "http://localhost:8000" : "";

export default function IssueCommunication() {
  const [issuer, setIssuer] = useState("SEBI");
  const [communicationType, setCommunicationType] = useState("circular");
  const [content, setContent] = useState("");
  const [result, setResult] = useState<IssueResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!content.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/authenticity/issue`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ issuer, communication_type: communicationType, content }),
      });
      if (!res.ok) throw new Error((await res.json()).detail ?? "Failed to issue communication");
      setResult(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to issue communication");
    } finally {
      setSubmitting(false);
    }
  };

  const reset = () => {
    setContent("");
    setResult(null);
    setError(null);
  };

  return (
    <>
      {!result && (
        <section className="upload-card">
          <h2>Issue an official communication</h2>
          <p className="muted">
            The "Layer 2: Authenticity Verification" half of the brief — a genuine communication gets a real Ed25519
            digital signature and a QR code. Anyone who receives it later can scan the QR (or enter the reference ID)
            to confirm it's genuine and unaltered, instead of only ever finding out after a fake one fooled them.
          </p>
          <label className="field-label-standalone">Issuer</label>
          <input className="text-field" value={issuer} onChange={(e) => setIssuer(e.target.value)} placeholder="e.g. SEBI, ABC Broking Ltd." />
          <label className="field-label-standalone">Communication type</label>
          <select className="text-field" value={communicationType} onChange={(e) => setCommunicationType(e.target.value)}>
            <option value="circular">Circular</option>
            <option value="advisory">Investor advisory</option>
            <option value="email">Official email</option>
            <option value="press_release">Press release</option>
          </select>
          <label className="field-label-standalone">Content</label>
          <textarea
            className="text-input"
            placeholder="Paste the official communication text…"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={6}
          />
          {error && <p className="error">{error}</p>}
          <button className="primary-btn" disabled={!content.trim() || submitting} onClick={handleSubmit}>
            {submitting ? "Signing…" : "Sign & Generate QR"}
          </button>
        </section>
      )}

      {result && (
        <section className="report">
          <div className="risk-banner risk-LOW">
            <img src={result.qr_data_uri} alt="Verification QR code" className="qr-image" />
            <div>
              <div className="risk-level">Digital Trust Certificate Issued</div>
              <p>
                Reference ID <span className="mono-text">{result.reference_id}</span>. Anyone can verify this
                communication at the link below, or by scanning the QR code.
              </p>
              <p className="mono-text muted">{result.verify_url}</p>
            </div>
          </div>
          <button className="link-btn" onClick={reset}>Issue another communication</button>
        </section>
      )}
    </>
  );
}
