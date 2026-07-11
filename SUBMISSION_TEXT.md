Ready-to-paste text for the SEBI Securities Market TechSprint registration form fields.

---

### Theme
SEBI Securities Market TechSprint

### Problem Statement
AI-Driven Detection of Synthetic Media

### Project Title
Synthetic Media Fraud Detector — Multi-Agent Forensic Triage for Market-Fraud Deepfakes

### Brief description of the idea
Deepfake and voice-cloned videos impersonating SEBI officials, well-known investors, and
registered advisors are circulating on WhatsApp, Telegram, and YouTube to push fraudulent
"guaranteed return" stock tips — a fraud pattern SEBI has already issued public advisories
about. Manual verification doesn't scale to the volume of clips being forwarded daily. We built
a multi-agent pipeline that takes a suspect video/audio clip and returns an evidence-backed fraud
risk score in under a minute: it transcribes the clip, extracts and fact-checks the claims made,
cross-references any named advisor against a registered-intermediary registry, scores the
audio/video for synthetic-media forensic artifacts, and synthesizes a grounded, human-readable
verdict — without ever treating the LLM's output as ground truth on its own.

### Proposed solution / Business model / commercial potential
The solution is a triage tool for SEBI's surveillance/enforcement teams and for brokerages'
compliance desks: instead of a human analyst watching every reported clip end-to-end, the tool
pre-scores incoming reports (from an investor-complaint channel, a social-media monitoring feed,
or direct upload) so analysts spend their time on the high-risk queue first. Commercially, this
is licensable to (a) SEBI/exchanges directly as a surveillance-augmentation tool, (b) brokerages
and mutual fund houses for brand-protection monitoring (detecting deepfakes of their own
spokespeople), and (c) media/fact-checking organizations covering financial misinformation. The
core IP — the auditable, explainable scoring engine that combines forensics + registry grounding
+ lexicon signals with an LLM narration layer — is model-agnostic and doesn't depend on any single
LLM vendor, which matters for a regulator that cannot depend on a single external API for a
production surveillance tool.

### Technology stack details
- **Backend**: Python, FastAPI, threaded job orchestrator for the agent pipeline
- **Media processing**: ffmpeg (audio/frame extraction), faster-whisper (speech-to-text)
- **Forensics**: librosa (audio signal processing — pitch jitter, spectral flatness, MFCC delta
  variance, silence-gap regularity), OpenCV (video — blink-toggle rate, face-region DCT frequency
  stability, brightness jitter)
- **Agentic/LLM layer**: Google Gemini (`gemini-2.5-flash`) with schema-constrained structured
  output for claims extraction and a grounded-generation risk-synthesis agent; deterministic
  regex/lexicon-based fallback when the LLM is unavailable, so the pipeline degrades gracefully
  rather than failing
- **Grounding**: rapidfuzz for fuzzy entity matching against a registered-intermediary registry
- **Frontend**: React + TypeScript (Vite), live pipeline visualization, evidence-based report UI
- **Explainability**: every risk-score component is a deterministic, auditable weighted signal;
  the LLM only narrates evidence that already exists in the structured output
