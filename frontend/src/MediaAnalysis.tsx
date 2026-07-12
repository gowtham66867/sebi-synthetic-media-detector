import { useCallback, useEffect, useRef, useState } from "react";
import { STAGE_LABELS, type JobStatus } from "./types";

const API_BASE = import.meta.env.DEV ? "http://localhost:8000" : "";
const STAGE_ORDER = ["extract", "transcribe", "claims", "forensics", "registry", "lexicon", "risk"];

export default function MediaAnalysis() {
  const [file, setFile] = useState<File | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  const handleSubmit = async () => {
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    setJob(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_BASE}/api/analyze`, { method: "POST", body: form });
      if (!res.ok) throw new Error((await res.json()).detail ?? "Upload failed");
      const data = await res.json();
      setJobId(data.job_id);
      stopPolling();
      pollRef.current = window.setInterval(() => pollJob(data.job_id), 1200);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const pollJob = async (id: string) => {
    const res = await fetch(`${API_BASE}/api/jobs/${id}`);
    if (!res.ok) return;
    const data: JobStatus = await res.json();
    setJob(data);
    if (data.status === "completed" || data.status === "failed") {
      stopPolling();
    }
  };

  const reset = () => {
    setFile(null);
    setJob(null);
    setJobId(null);
    setUploadError(null);
    stopPolling();
  };

  return (
    <>
      {!jobId && (
        <section className="upload-card">
          <h2>Analyze a suspect clip</h2>
          <p className="muted">
            Upload a video or audio clip (e.g. a WhatsApp/Telegram forward claiming stock tips, or an official
            impersonation). The pipeline transcribes it, extracts claims, cross-checks against a registered
            intermediary registry, and scores synthetic-media forensic artifacts.
          </p>
          <label className="dropzone">
            <input type="file" accept="video/*,audio/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            {file ? <span>{file.name}</span> : <span>Click to choose a video or audio file</span>}
          </label>
          {uploadError && <p className="error">{uploadError}</p>}
          <button className="primary-btn" disabled={!file || uploading} onClick={handleSubmit}>
            {uploading ? "Uploading…" : "Run Analysis"}
          </button>
        </section>
      )}

      {jobId && job && (
        <>
          <section className="pipeline">
            <div className="pipeline-header">
              <h2>Agent Pipeline</h2>
              <button className="link-btn" onClick={reset}>Analyze another clip</button>
            </div>
            <div className="stage-row">
              {STAGE_ORDER.map((s) => (
                <div key={s} className={`stage-pill stage-${job.stages[s]}`}>
                  <span className="dot" />
                  {STAGE_LABELS[s]}
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

          {job.status === "completed" && job.result && <Report report={job.result} />}
        </>
      )}
    </>
  );
}

function Report({ report }: { report: NonNullable<JobStatus["result"]> }) {
  const pct = Math.round(report.risk_score * 100);
  return (
    <section className="report">
      <div className={`risk-banner risk-${report.risk_level}`}>
        <div className="risk-score">{pct}<span>/100</span></div>
        <div>
          <div className="risk-level">{report.risk_level} RISK</div>
          <p>{report.summary}</p>
        </div>
      </div>

      <div className="grid">
        <div className="card">
          <h3>Media Forensics</h3>
          <ScoreBar label="Synthetic voice score" value={report.media_forensics.audio.synthetic_voice_score} />
          <ul className="notes">{report.media_forensics.audio.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
          <ScoreBar label="Synthetic video score" value={report.media_forensics.video.synthetic_video_score} />
          <ul className="notes">{report.media_forensics.video.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </div>

        <div className="card">
          <h3>Extracted Claims (LLM Agent)</h3>
          <p className="field-label">Overall intent</p>
          <p className="chip">{report.transcript_claims.overall_intent}</p>
          <p className="field-label">Claimed entities</p>
          <ul>
            {report.transcript_claims.claimed_entities.map((e, i) => (
              <li key={i}>{e.name} <span className="muted">({e.role_guess})</span></li>
            ))}
            {report.transcript_claims.claimed_entities.length === 0 && <li className="muted">None detected</li>}
          </ul>
          <p className="field-label">Financial claims</p>
          <ul>
            {report.transcript_claims.financial_claims.map((c, i) => <li key={i}>{c}</li>)}
            {report.transcript_claims.financial_claims.length === 0 && <li className="muted">None detected</li>}
          </ul>
        </div>

        <div className="card">
          <h3>Registry Cross-Check</h3>
          {report.registry_matches.filter((m) => m.verdict !== "not_applicable").length === 0 && (
            <p className="muted">No identifiable named individuals to check.</p>
          )}
          {report.registry_matches
            .filter((m) => m.verdict !== "not_applicable")
            .map((m, i) => (
              <div key={i} className={`registry-row verdict-${m.verdict}`}>
                <div className="registry-name">{m.claimed_name}</div>
                <div className="registry-verdict">{m.verdict.replaceAll("_", " ")}</div>
                <div className="muted">match score: {m.match_score.toFixed(0)}</div>
              </div>
            ))}
        </div>

        <div className="card">
          <h3>Scam Lexicon Hits</h3>
          {Object.keys(report.lexicon_hits).length === 0 && <p className="muted">No red-flag phrases matched.</p>}
          {Object.entries(report.lexicon_hits).map(([cat, phrases]) => (
            <div key={cat} className="lexicon-cat">
              <span className="chip warn">{cat.replaceAll("_", " ")}</span>
              <span className="muted"> — "{phrases.join('", "')}"</span>
            </div>
          ))}
        </div>
      </div>

      <div className="card transcript-card">
        <h3>Transcript ({report.transcript.language}, confidence {(report.transcript.language_probability * 100).toFixed(0)}%)</h3>
        <p className="transcript-text">{report.transcript.full_text || <span className="muted">No speech detected.</span>}</p>
      </div>
    </section>
  );
}

export function ScoreBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100);
  const cls = pct >= 66 ? "bar-high" : pct >= 35 ? "bar-med" : "bar-low";
  return (
    <div className="score-bar-wrap">
      <div className="score-bar-label"><span>{label}</span><span>{pct}%</span></div>
      <div className="score-bar-track"><div className={`score-bar-fill ${cls}`} style={{ width: `${pct}%` }} /></div>
    </div>
  );
}
