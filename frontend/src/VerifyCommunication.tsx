import { useEffect, useState } from "react";
import type { VerifyResponse } from "./types";

const API_BASE = import.meta.env.DEV ? "http://localhost:8000" : "";

export default function VerifyCommunication({ initialReferenceId }: { initialReferenceId?: string }) {
  const [referenceId, setReferenceId] = useState(initialReferenceId ?? "");
  const [result, setResult] = useState<VerifyResponse | null>(null);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const checkReference = async (id: string) => {
    if (!id.trim()) return;
    setChecking(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/authenticity/verify/${encodeURIComponent(id.trim())}`);
      if (!res.ok) throw new Error("Verification lookup failed");
      setResult(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification lookup failed");
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => {
    if (initialReferenceId) checkReference(initialReferenceId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialReferenceId]);

  return (
    <section className="upload-card">
      <h2>Verify a communication</h2>
      <p className="muted">
        Enter the reference ID from a QR code or an official communication to confirm it's genuine and unaltered —
        the public-facing half of "Layer 2: Authenticity Verification."
      </p>
      <div className="verify-input-row">
        <input
          className="text-field"
          value={referenceId}
          onChange={(e) => setReferenceId(e.target.value)}
          placeholder="Reference ID, e.g. 4f6a1c2e9b0d"
          onKeyDown={(e) => e.key === "Enter" && checkReference(referenceId)}
        />
        <button className="primary-btn" disabled={!referenceId.trim() || checking} onClick={() => checkReference(referenceId)}>
          {checking ? "Checking…" : "Verify"}
        </button>
      </div>
      {error && <p className="error">{error}</p>}

      {result && (
        <div className={`risk-banner ${result.verified ? "risk-LOW" : "risk-HIGH"}`} style={{ marginTop: 20 }}>
          <div className="risk-score" style={{ fontSize: "2rem" }}>{result.verified ? "✓" : "✗"}</div>
          <div>
            <div className="risk-level">{result.verified ? "Authenticity Confirmed" : "Not Verified"}</div>
            {result.verified ? (
              <>
                <p>
                  Issued by <strong>{result.issuer}</strong> ({result.communication_type}) on{" "}
                  {result.issued_at && new Date(result.issued_at).toLocaleString()}.
                </p>
                <p className="transcript-text" style={{ marginTop: 10 }}>{result.content}</p>
              </>
            ) : (
              <p>
                {result.reason === "reference_not_found"
                  ? "No record found for this reference ID — this may be a fabricated or mistyped reference."
                  : "The signature on this record does not match its content — it may have been tampered with."}
              </p>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
