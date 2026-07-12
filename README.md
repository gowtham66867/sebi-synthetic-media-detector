# Synthetic Media Fraud Detector

**SEBI Securities Market TechSprint — Problem Statement: AI-Driven Detection of Synthetic Media**

**Live demo**: https://sebi-synthetic-media-detector-564262191703.asia-south1.run.app
**Source**: https://github.com/gowtham66867/sebi-synthetic-media-detector

Detects deepfake / voice-cloned video and audio clips that impersonate SEBI officials, registered
advisors, or public figures to push fraudulent stock tips (a documented, escalating fraud pattern
in Indian markets — fake videos of well-known investors/regulators circulate on WhatsApp and
YouTube pushing "guaranteed return" penny stocks).

## Why this problem statement

Of the four TechSprint problem statements, this one was chosen because it is simultaneously the
most **topical** (SEBI has issued live advisories on exactly this fraud pattern), the most
**technically differentiated** (multimodal forensics + agentic reasoning, vs. "another investment
app" for the Super App statement), and the most **demoable** (a judge can watch a suspect clip go
in and a scored, evidence-backed verdict come out in under a minute).

## Architecture — multi-agent pipeline

```
Upload → Extract (ffmpeg) → Transcribe (faster-whisper)
                                     │
                    ┌────────────────┼─────────────────┐
                    ▼                ▼                 ▼
         Claims Agent (LLM)   Audio Forensics    Video Forensics
        entities/claims/red      (librosa)          (opencv)
           flags, intent      voice-clone tells   face-swap tells
                    │                │                 │
                    ▼                │                 │
         Registry Cross-Check        │                 │
        (fuzzy match vs mock          │                 │
         SEBI intermediary DB)        │                 │
                    │                │                 │
                    └────────┬───────┴─────────────────┘
                             ▼
                    Scam Lexicon Scan (deterministic)
                             │
                             ▼
                  Risk Synthesis Agent (LLM)
          weighted scoring (auditable) + grounded
             natural-language explanation
                             │
                             ▼
                  Score + evidence report → UI
```

Each stage is an independently testable "agent" in the loose sense used throughout this build:
a component with a narrow contract that the orchestrator (`backend/app/services/orchestrator.py`)
wires into a pipeline, with per-stage progress exposed to the frontend for a live visualization.

### Advanced concepts demonstrated

- **Agentic orchestration**: a Python orchestrator coordinates seven independent stages (two of
  them LLM-backed, five deterministic), each individually testable, with typed data contracts
  between them rather than passing raw strings around.
- **Structured LLM extraction (schema-constrained generation)**: the claims agent forces Gemini to
  return JSON matching a strict schema (entities + role, claims, red-flag phrases, intent) — no
  parsing of free text, no hallucinated shape.
- **Grounded generation**: the final risk-synthesis agent is given only the structured evidence
  dict and is explicitly instructed not to invent evidence — the summary it writes has to point at
  numbers that actually exist in the pipeline's output.
- **Multimodal forensics without a black-box model**: rather than a deep classifier requiring a
  large labeled deepfake dataset and GPU training (infeasible in a hackathon timeframe), the audio
  and video forensics modules compute the same signal-processing features real forensic
  classifiers are seeded with — pitch jitter, spectral flatness, MFCC delta variance, silence-gap
  regularity for audio; blink-toggle rate, face-region DCT frequency stability, brightness jitter
  for video. Every number in the report is explainable and defensible, not a black-box confidence
  score.
- **RAG-style grounding against ground truth**: claimed identities are fuzzy-matched
  (`rapidfuzz`) against a registered-intermediary registry rather than trusted at face value —
  the same shape of check a live integration with SEBI's actual intermediary lookup would perform.
- **Graceful degradation**: both LLM call sites (`app/services/llm_client.py`) fall back to a
  deterministic rule-based extractor / templated summary if the API is unavailable (quota, auth,
  network) — the pipeline never hard-fails just because an LLM call did. This was a real failure
  mode hit during development (multiple API keys ran out of quota) and turned into a resilience
  feature worth highlighting to judges: a live demo degrades gracefully instead of crashing.
- **Auditable scoring**: the final risk score is a deterministic weighted combination of every
  upstream signal (not an LLM-invented number), so it's reproducible and defensible to a
  regulator's compliance/audit function — the LLM only narrates the *why*.

## Running it

```bash
# Backend
cd backend
source venv/bin/activate   # venv already created + deps installed
uvicorn app.main:app --port 8000

# Frontend (separate terminal)
cd frontend
npm run dev -- --port 5180
```

Open `http://localhost:5180`, upload a video/audio clip, watch the pipeline run.

## Deployment

Single container (multi-stage `Dockerfile`: builds the frontend, bakes the faster-whisper model in
so cold starts don't hit HuggingFace, serves the built frontend + API from one FastAPI process).
Deployed to Cloud Run via the committed `deploy.sh`:

```bash
gcloud secrets create sebi-synthetic-media-gemini-key --data-file=- <<< "$GEMINI_API_KEY"
gcloud secrets add-iam-policy-binding sebi-synthetic-media-gemini-key \
  --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

GCP_PROJECT=your-project ./deploy.sh
```

`--no-cpu-throttling` matters: the pipeline runs in a background thread after the HTTP response
returns, and Cloud Run only allocates CPU during active request handling by default — without
this flag the background pipeline stalls between polls instead of actually progressing. This is
baked into `deploy.sh` rather than left as something to remember by hand.

Job state lives in Firestore (`app/services/job_store.py`), not in a process-local dict — the
in-memory version silently 404'd real in-progress jobs the moment Cloud Run ran more than one
instance, since a poll could land on an instance that never ran the job. Local dev without GCP
credentials falls back to the in-memory store automatically; the same graceful-degradation pattern
used for the LLM call sites.

Requires `ffmpeg` (installed via `brew install ffmpeg`) and a `GEMINI_API_KEY` in the repo-root
`.env` (falls back to rule-based extraction/summary automatically if absent or quota-exhausted).

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

33 cases covering forensics edge cases, lexicon scanning, registry fuzzy-match thresholds,
risk-engine scoring/caps, LLM-fallback behavior, rate limiting, and API-level input validation
(400/404/413/429) — none of them require network access, ffmpeg, or a real Gemini key.

## A small honest validation of the forensics heuristics

"We never checked this against a real clip" was a fair criticism of the first version of this
project. `backend/scripts/validate_forensics.py` runs a small, explicitly-not-rigorous check: 5
TTS clips (macOS `say`, 5 different voices) against 5 real human-speech clips (public-domain
LibriVox recordings, via Archive.org). Result from one run:

| set                | scores                          | mean  |
|---------------------|----------------------------------|-------|
| synthetic (TTS)     | 0.165, 0.235, 0.212, 0.219, 0.265 | 0.219 |
| real (human speech) | 0.181, 0.210, 0.134, 0.091, 0.051 | 0.133 |

The synthetic mean is higher, so there's real directional signal — but the two distributions
overlap (the real set's highest score, 0.210, sits inside the synthetic set's range). At n=5 per
class this is evidence worth following up, not proof the heuristics work. Treat the forensic
scores as a first-pass explainable filter, not a validated classifier, until this is run against
something like ASVspoof at real scale.

## What's mocked vs. real for this prototype

- **Real**: media extraction, Whisper transcription, all audio/video forensic feature extraction
  (given a small, honest, non-rigorous validation — see above), fuzzy registry matching logic,
  lexicon scanning, weighted risk scoring, LLM structured extraction and synthesis, per-IP rate
  limiting on the compute-triggering endpoint, the full agentic pipeline and live UI.
- **Mocked** (clearly labeled, swappable for production): the SEBI registered-intermediary list
  (`backend/data/registered_advisors.csv`) stands in for SEBI's real intermediary lookup API/SCORES
  database — the fuzzy-match cross-check logic is identical to what a live integration would run.
  Checked during this build: SEBI does not publish a bulk-downloadable open dataset of registered
  intermediaries, only a lookup portal (siportal.sebi.gov.in) — a real integration needs an actual
  API partnership, not more code.

## Next steps for a production version

- Swap the mock registry CSV for SEBI's real registered-intermediary API.
- Replace the heuristic forensics scores with an ensemble that also includes a trained deepfake
  classifier (e.g. fine-tuned on FaceForensics++/ASVspoof) once labeled data and GPU budget exist —
  the current heuristics are designed to be a first-pass, explainable filter, not a final word.
- Add a feedback loop where analyst verdicts (confirmed fraud / false positive) retrain the
  weighting in `risk_engine.py`.
- Ingest directly from WhatsApp Business API / YouTube Data API tip lines instead of manual upload.
- Add real authentication once this moves past demo/triage use — the rate limiter
  (`app/services/rate_limiter.py`) caps abuse per IP but is deliberately not a substitute for auth,
  and is per-instance rather than Firestore-backed (a deliberate tradeoff: worth revisiting if this
  ever needs to enforce a hard per-tenant quota rather than casual abuse protection on a demo).
