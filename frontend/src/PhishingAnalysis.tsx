import { useCallback, useEffect, useRef, useState } from "react";
import { PHISHING_STAGE_LABELS, type PhishingJobStatus, type PhishingReport } from "./types";
import { ScoreBar } from "./MediaAnalysis";

const API_BASE = import.meta.env.DEV ? "http://localhost:8000" : "";
const STAGE_ORDER = ["claims", "lexicon", "risk"];

const SAMPLE_TEXT =
  "Dear Customer,\nThis is an official SEBI compliance team notice. Your account will be suspended within 24 " +
  "hours unless you verify your account immediately. Click the link below to update your KYC:\n" +
  "https://sebi-verify-kyc.example.com/login\nRegards, Compliance Team";

export default function PhishingAnalysis() {
  const [text, setText] = useState("");
  const [job, setJob] = useState<PhishingJobStatus | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  const handleSubmit = async () => {
    if (!text.trim()) return;
    setSubmitting(true);
    setSubmitError(null);
    setJob(null);
    try {
      const res = await fetch(`${API_BASE}/api/phishing/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!res.ok) throw new Error((await res.json()).detail ?? "Submission failed");
      const data = await res.json();
      setJobId(data.job_id);
      stopPolling();
      pollRef.current = window.setInterval(() => pollJob(data.job_id), 1000);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Submission failed");
    } finally {
      setSubmitting(false);
    }
  };

  const pollJob = async (id: string) => {
    const res = await fetch(`${API_BASE}/api/phishing/jobs/${id}`);
    if (!res.ok) return;
    const data: PhishingJobStatus = await res.json();
    setJob(data);
    if (data.status === "completed" || data.status === "failed") {
      stopPolling();
    }
  };

  const reset = () => {
    setText("");
    setJob(null);
    setJobId(null);
    setSubmitError(null);
    stopPolling();
  };

  return (
    <>
      {!jobId && (
        <section className="upload-card">
          <h2>Analyze a suspicious email or message</h2>
          <p className="muted">
            Paste a suspicious email, SMS, or WhatsApp message claiming to be from SEBI, a broker, or a relationship
            manager. The pipeline extracts the claimed sender, links, and requested actions, scans for phishing
            language, and scores the risk.
          </p>
          <textarea
            className="text-input"
            placeholder="Paste the suspicious message here…"
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={8}
          />
          <div className="text-input-actions">
            <button className="link-btn" onClick={() => setText(SAMPLE_TEXT)}>Use a sample phishing message</button>
          </div>
          {submitError && <p className="error">{submitError}</p>}
          <button className="primary-btn" disabled={!text.trim() || submitting} onClick={handleSubmit}>
            {submitting ? "Submitting…" : "Run Analysis"}
          </button>
        </section>
      )}

      {jobId && job && (
        <>
          <section className="pipeline">
            <div className="pipeline-header">
              <h2>Agent Pipeline</h2>
              <button className="link-btn" onClick={reset}>Analyze another message</button>
            </div>
            <div className="stage-row">
              {STAGE_ORDER.map((s) => (
                <div key={s} className={`stage-pill stage-${job.stages[s]}`}>
                  <span className="dot" />
                  {PHISHING_STAGE_LABELS[s]}
                </div>
              ))}
            </div>
          </section>

          {job.status === "failed" && (
            <section className="error-card">
              <h3>Analysis failed</h3>
              <pre>{job.error}</pre>
            </section>
          )}

          {job.status === "completed" && job.result && <PhishingReportView report={job.result} />}
        </>
      )}
    </>
  );
}

function PhishingReportView({ report }: { report: PhishingReport }) {
  const claims = report.phishing_claims;

  if (report.risk_level === "OUT_OF_SCOPE") {
    return (
      <section className="report">
        <div className="risk-banner risk-OUT_OF_SCOPE">
          <div className="risk-score" style={{ fontSize: "1.6rem" }}>⚠</div>
          <div>
            <div className="risk-level">OUTSIDE THIS TOOL'S SCOPE</div>
            <p>{report.summary}</p>
          </div>
        </div>
        {report.severe_content_hits && Object.keys(report.severe_content_hits).length > 0 && (
          <div className="card">
            <h3>Flagged Language</h3>
            {Object.entries(report.severe_content_hits).map(([cat, phrases]) => (
              <div key={cat} className="lexicon-cat">
                <span className="chip warn">{cat.replaceAll("_", " ")}</span>
                <span className="muted"> — "{phrases.join('", "')}"</span>
              </div>
            ))}
          </div>
        )}
        <div className="card transcript-card">
          <h3>Message Text</h3>
          <p className="transcript-text">{report.message_text}</p>
        </div>
      </section>
    );
  }

  const pct = Math.round(report.risk_score * 100);
  return (
    <section className="report">
      <div className={`risk-banner risk-${report.risk_level}`}>
        <div className="risk-score">{pct}<span>/100</span></div>
        <div>
          <div className="risk-level">{report.risk_level} RISK — {claims.verdict.replaceAll("_", " ")}</div>
          <p>{report.summary}</p>
        </div>
      </div>

      <div className="grid">
        <div className="card">
          <h3>Extracted Indicators (LLM Agent)</h3>
          <p className="field-label">Claimed sender</p>
          <p className="chip">{claims.claimed_sender ?? "None stated"}</p>
          <p className="field-label">URLs found</p>
          <ul>
            {claims.urls_found.map((u, i) => <li key={i} className="mono-text">{u}</li>)}
            {claims.urls_found.length === 0 && <li className="muted">None detected</li>}
          </ul>
          <p className="field-label">Requested actions</p>
          <ul>
            {claims.requested_actions.map((a, i) => <li key={i}>{a}</li>)}
            {claims.requested_actions.length === 0 && <li className="muted">None detected</li>}
          </ul>
        </div>

        <div className="card">
          <h3>Phishing Lexicon Hits</h3>
          {Object.keys(report.lexicon_hits).length === 0 && <p className="muted">No red-flag phrases matched.</p>}
          {Object.entries(report.lexicon_hits).map(([cat, phrases]) => (
            <div key={cat} className="lexicon-cat">
              <span className="chip warn">{cat.replaceAll("_", " ")}</span>
              <span className="muted"> — "{phrases.join('", "')}"</span>
            </div>
          ))}
          <ScoreBar label="Overall phishing risk" value={report.risk_score} />
        </div>
      </div>

      <div className="card transcript-card">
        <h3>Message Text</h3>
        <p className="transcript-text">{report.message_text}</p>
      </div>
    </section>
  );
}
