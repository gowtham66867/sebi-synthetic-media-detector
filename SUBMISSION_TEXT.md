Ready-to-paste text for the SEBI Securities Market TechSprint registration form fields.

**Live demo**: https://sebi-synthetic-media-detector-564262191703.asia-south1.run.app
**Source code**: https://github.com/gowtham66867/sebi-synthetic-media-detector

---

### Theme
SEBI Securities Market TechSprint

### Problem Statement
AI-Driven Detection of Synthetic Media and Phishing Attacks in Securities Markets — Building Trust in the AI Era

### Project Title
Dual Protection Framework — AI Threat Detection & Digital Authenticity Verification for Securities Markets

### Brief description of the idea
The brief names five AI-enabled fraud vectors hitting securities markets today: phishing emails
impersonating SEBI/brokers, voice-cloned relationship managers, deepfake CEO videos pushing stock
moves, AI-generated fake "breaking news" about listed companies, and forged regulatory circulars.
Existing cybersecurity tooling catches conventional attacks but doesn't verify whether the content
of a financial communication is itself authentic or AI-generated. We built both halves of the
brief's requested Dual Protection Framework: Layer 1 (AI Threat Detection) — a multi-agent pipeline
that scores suspect video/audio clips for deepfake/voice-clone forensic artifacts and cross-checks
claimed identities against a registered-intermediary registry, plus a parallel pipeline that scores
suspicious emails/messages for phishing indicators — and Layer 2 (Authenticity Verification) — real
Ed25519 digital signatures and QR-coded verification, so a genuine SEBI circular or broker
communication can prove itself authentic instead of investors only ever finding out a fake one
fooled them after the fact.

### Proposed solution / Business model / commercial potential
Layer 1 is a triage tool for SEBI's surveillance/enforcement teams and brokerages' compliance
desks: instead of a human analyst reviewing every reported clip or forwarded email end-to-end, the
tool pre-scores incoming reports so analysts spend their time on the high-risk queue first. Layer 2
is the complementary product for the issuing side: SEBI, exchanges, and brokers sign outgoing
official communications once, and every recipient (investor, journalist, another broker) can
verify authenticity instantly via a QR scan — no app install, no account needed on the verifying
side. Commercially, Layer 1 is licensable to SEBI/exchanges as a surveillance-augmentation tool and
to brokerages for brand-protection monitoring (detecting deepfakes/phishing impersonating their own
staff); Layer 2 is licensable as an authenticated-communications product to any regulated entity
that issues circulars, advisories, or investor communications at scale. The two layers are
deliberately sold together: detection without authentication only ever tells you something was
fake after the damage; authentication without detection does nothing for the fraud already in
circulation. The scoring/signing engines are model-agnostic (the LLM layer has a deterministic
fallback) and the cryptography is standard Ed25519, not a proprietary scheme — nothing here locks
a regulator into a single vendor.

### Technology stack details
- **Backend**: Python, FastAPI, threaded orchestrators for two independent agent pipelines (media
  forensics, phishing text)
- **Media processing**: ffmpeg (audio/frame extraction), faster-whisper (speech-to-text)
- **Forensics**: librosa (audio signal processing — pitch jitter, spectral flatness, MFCC delta
  variance, silence-gap regularity), OpenCV (video — blink-toggle rate, face-region DCT frequency
  stability, brightness jitter)
- **Agentic/LLM layer**: Google Gemini (`gemini-2.5-flash`) with schema-constrained structured
  output for both claims extraction (media) and phishing-indicator extraction (text), plus
  grounded-generation risk-synthesis agents; deterministic regex/lexicon-based fallback for both
  when the LLM is unavailable, so the pipeline degrades gracefully rather than failing
- **Grounding**: rapidfuzz for fuzzy entity matching against a registered-intermediary registry
- **Authenticity layer**: `cryptography` (Ed25519 digital signatures over a SHA-256 content hash),
  `qrcode` for QR generation, Google Secret Manager for the production signing key
- **Persistence**: Google Firestore for job state and issued authenticity records, shared correctly
  across Cloud Run instances (not an in-memory store that would silently lose state under scaling)
- **Frontend**: React + TypeScript (Vite), live pipeline visualization, evidence-based report UI,
  plus a public `/verify/:id` route reachable directly by scanning a QR code
- **Explainability**: every risk-score component in both detection pipelines is a deterministic,
  auditable weighted signal; the LLM only narrates evidence that already exists in the structured
  output
- **Testing**: 54 automated pytest cases, all offline (mocked LLM calls), including Ed25519
  tamper-detection tests and a small honest validation of the forensic heuristics against real
  public-domain human speech
