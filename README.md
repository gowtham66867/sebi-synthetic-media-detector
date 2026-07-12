# AI-Driven Detection of Synthetic Media and Phishing Attacks in Securities Markets

**SEBI Securities Market TechSprint 2026 — Building Trust in the AI Era**

**Live demo**: https://sebi-synthetic-media-detector-564262191703.asia-south1.run.app
**Source**: https://github.com/gowtham66867/sebi-synthetic-media-detector

The official brief asks for a **Dual Protection Framework**:

- **Layer 1 — AI Threat Detection**: detect phishing emails, deepfake videos, cloned voices, fake
  investment ads, and AI-generated social-media campaigns.
- **Layer 2 — Authenticity Verification**: let genuine communications prove they're genuine —
  digital signatures, QR verification, a public verification portal — instead of only ever telling
  people after the fact that something was fake.

This build implements both layers, not just the detection half:

| Capability (from the brief) | Where it lives |
|---|---|
| Deepfake video / cloned voice detection | `app/services/forensics_audio.py`, `forensics_video.py` |
| Fake investment advertisement detection | `app/services/claims_agent.py`, `risk_engine.py` |
| AI phishing email detection | `app/services/phishing_agent.py`, `phishing_risk_engine.py` |
| Digital Trust Certificate / Digital Signature | `app/services/authenticity.py` (real Ed25519 signing) |
| QR Verification / Public Verification Portal | `app/services/qr.py`, `app/routers/authenticity.py`, `/verify/:id` |

Four things you can do in the live demo, matching the brief's workflow diagram (Official
Communication → Digital Signature/QR → AI Detection Engine → Suspicious Activity Detected /
Authenticity Confirmed):

1. **Suspect Clip** — upload a video/audio clip claiming to be an official/advisor; get a
   deepfake/voice-clone forensic score.
2. **Suspicious Message** — paste an email/SMS/WhatsApp message; get a phishing risk score.
3. **Issue Communication** — sign a genuine communication, get a QR code + reference ID.
4. **Verify Communication** — scan that QR (or type the reference ID) to confirm it's genuine.

## Architecture

Three independent pipelines, sharing infrastructure (Firestore job store, Gemini client with
rule-based fallback, rate limiter) but each with its own contract, since a video clip, a text
message, and a signing request genuinely don't share stages.

### Layer 1a — media (deepfake / voice-clone) pipeline

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

Orchestrated by `app/services/orchestrator.py`.

### Layer 1b — phishing (email/message) pipeline

```
Message text → Claims Agent (LLM)          → Phishing Lexicon Scan  → Risk Synthesis Agent (LLM)
                claimed sender, URLs,          credential harvesting,   weighted scoring + grounded
                requested actions,             urgency, impersonation,  explanation
                red flags, verdict             financial requests
```

Orchestrated by `app/services/text_orchestrator.py` — deliberately a separate, shorter pipeline
(3 stages, not 7) rather than forcing text through the media pipeline's audio/video-specific
stages.

### Layer 2 — authenticity verification

```
Issuer submits content → Ed25519 sign over SHA-256(content) → Firestore record + reference ID
                                                                        │
                                                                        ▼
                                                            QR code encoding /verify/:id
                                                                        │
                                    ┌───────────────────────────────────┘
                                    ▼
                    Anyone scans QR / enters reference ID
                                    │
                                    ▼
                    Re-verify signature against stored content
                                    │
                        ┌───────────┴───────────┐
                        ▼                       ▼
              Authenticity Confirmed     Not Verified (tampered
                                          or reference not found)
```

`app/services/authenticity.py` + `app/routers/authenticity.py`. This is the half of the brief
("Layer 2: Authenticity Verification" — digital signatures, QR verification, a public
verification portal) that's easy to skip because detecting fakes is the more obvious/exciting
half — but the brief asks for both, and a system that only ever detects fakes never lets a
genuine communication prove itself.

Each stage in both detection pipelines is an independently testable "agent" in the loose sense
used throughout this build: a component with a narrow contract that an orchestrator wires
together, with per-stage progress exposed to the frontend for a live visualization.

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
- **Real asymmetric cryptography for Layer 2**: `app/services/authenticity.py` signs a SHA-256
  hash of the content with Ed25519, not a hash-only "trust me" scheme — verification re-checks the
  signature against the stored content, so a tampered record fails verification even if someone
  guesses or copies a valid reference ID.
- **Detection and authentication share infrastructure, not code paths**: both new capabilities
  reuse the existing Firestore-backed store pattern, the same LLM-with-fallback client, and the
  same rate limiter — but get their own pipelines/routers rather than being forced through the
  media pipeline's stages, which don't apply to text or to a signing request.

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

Open `http://localhost:5180`. If `JOB_STORE=memory` isn't set and you don't have GCP Application
Default Credentials configured, first backend startup will hang for a while trying (and failing)
to reach Firestore before falling back — set `JOB_STORE=memory` for a fast local loop:

```bash
JOB_STORE=memory uvicorn app.main:app --port 8000
```

## Deployment

Single container (multi-stage `Dockerfile`: builds the frontend, bakes the faster-whisper model in
so cold starts don't hit HuggingFace, serves the built frontend + API from one FastAPI process).
Deployed to Cloud Run via the committed `deploy.sh`:

```bash
gcloud secrets create sebi-synthetic-media-gemini-key --data-file=- <<< "$GEMINI_API_KEY"
gcloud secrets create sebi-synthetic-media-signing-key --data-file=- <<< "$SIGNING_PRIVATE_KEY_PEM"
gcloud secrets add-iam-policy-binding sebi-synthetic-media-gemini-key \
  --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding sebi-synthetic-media-signing-key \
  --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

GCP_PROJECT=your-project ./deploy.sh
```

`--no-cpu-throttling` matters: the pipelines run in a background thread after the HTTP response
returns, and Cloud Run only allocates CPU during active request handling by default — without
this flag the background pipeline stalls between polls instead of actually progressing. This is
baked into `deploy.sh` rather than left as something to remember by hand.

`PUBLIC_BASE_URL` matters for Layer 2 specifically — it's baked into every QR code as the
verification URL. `deploy.sh` defaults it to this service's known Cloud Run URL; override it if
you deploy a fork elsewhere.

Job state and authenticity records both live in Firestore (`app/services/job_store.py`,
`authenticity_store.py`), not in a process-local dict — the in-memory version silently 404'd real
in-progress jobs (or unverifiable records) the moment Cloud Run ran more than one instance, since
a request could land on an instance that never created them. Local dev without GCP credentials
falls back to the in-memory store automatically; the same graceful-degradation pattern used for
the LLM call sites and for the signing key (see below).

Requires `ffmpeg` (installed via `brew install ffmpeg`), a `GEMINI_API_KEY`, and ideally a
`SIGNING_PRIVATE_KEY_PEM` in the repo-root `.env`. Without the Gemini key, extraction/summary falls
back to rule-based logic automatically. Without the signing key, an ephemeral keypair is generated
at startup — fine for local dev, but anything signed won't verify after a restart, so production
must set the real key.

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
JOB_STORE=memory pytest
```

54 cases covering forensics edge cases, lexicon scanning (both scam and phishing lexicons),
registry fuzzy-match thresholds, risk-engine scoring/caps (both risk engines), LLM-fallback
behavior, rate limiting, Ed25519 sign/verify (including tamper detection), and API-level input
validation (400/404/413/422/429) — none of them require network access, ffmpeg, or a real Gemini
key.

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
  lexicon scanning (scam + phishing), weighted risk scoring (both engines), LLM structured
  extraction and synthesis, per-IP rate limiting on both compute-triggering endpoints, real Ed25519
  digital signatures with tamper detection, real QR codes encoding a working verification URL, the
  full agentic pipelines and live UI.
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
  weighting in `risk_engine.py` and `phishing_risk_engine.py`.
- Ingest directly from WhatsApp Business API / YouTube Data API tip lines and a real mail
  transport (IMAP/mailbox integration) instead of manual upload/paste for both detection layers.
- Add real authentication once this moves past demo/triage use — the rate limiter
  (`app/services/rate_limiter.py`) caps abuse per IP but is deliberately not a substitute for auth,
  and is per-instance rather than Firestore-backed (a deliberate tradeoff: worth revisiting if this
  ever needs to enforce a hard per-tenant quota rather than casual abuse protection on a demo).
- For Layer 2 at real scale: publish the public key so third parties can verify signatures
  independently rather than only via this service's own `/verify` endpoint, and consider a proper
  PKI/certificate-authority model if multiple issuers (SEBI, individual brokers) need distinct,
  independently-revocable signing identities rather than one shared key.
- Detect AI-generated social-media posts and fake regulatory circulars specifically (currently
  covered only incidentally by the phishing lexicon/claims agent, not purpose-built for those
  formats) — the two other Layer 1 sub-capabilities named in the brief this build doesn't have a
  dedicated pipeline for.
