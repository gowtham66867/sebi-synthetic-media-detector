export type StageStatus = "pending" | "running" | "done";

export interface JobStatus {
  status: "running" | "completed" | "failed";
  stages: Record<string, StageStatus>;
  result: RiskReport | null;
  error: string | null;
}

export interface RegistryMatchView {
  claimed_name: string;
  match_score: number;
  verdict: "verified_active" | "verified_but_expired_or_suspended" | "no_match" | "not_applicable";
  matched_record: Record<string, string> | null;
}

export interface RiskReport {
  risk_score: number;
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  summary: string;
  media_forensics: {
    audio: { synthetic_voice_score: number; signals: Record<string, number | null>; notes: string[] };
    video: { synthetic_video_score: number; signals: Record<string, number | null>; notes: string[] };
  };
  transcript_claims: {
    claimed_entities: { name: string; role_guess: string }[];
    financial_claims: string[];
    red_flag_phrases: string[];
    overall_intent: string;
  };
  registry_matches: RegistryMatchView[];
  lexicon_hits: Record<string, string[]>;
  transcript: { full_text: string; language: string; language_probability: number };
}

export const STAGE_LABELS: Record<string, string> = {
  extract: "Extract Media",
  transcribe: "Transcribe Audio",
  claims: "Extract Claims (Agent)",
  forensics: "Media Forensics",
  registry: "Registry Cross-Check",
  lexicon: "Scam Lexicon Scan",
  risk: "Risk Synthesis (Agent)",
};

export interface PhishingReport {
  risk_score: number;
  risk_level: "LOW" | "MEDIUM" | "HIGH" | "OUT_OF_SCOPE";
  summary: string;
  phishing_claims: {
    claimed_sender: string | null;
    urls_found: string[];
    requested_actions: string[];
    red_flag_phrases: string[];
    verdict: "likely_phishing" | "suspicious" | "likely_legitimate" | "unclear";
    extraction_method: "llm" | "rule_based_fallback";
  };
  lexicon_hits: Record<string, string[]>;
  severe_content_hits?: Record<string, string[]>;
  message_text: string;
}

export interface PhishingJobStatus {
  status: "running" | "completed" | "failed";
  stages: Record<string, StageStatus>;
  result: PhishingReport | null;
  error: string | null;
}

export const PHISHING_STAGE_LABELS: Record<string, string> = {
  claims: "Extract Indicators (Agent)",
  lexicon: "Phishing Lexicon Scan",
  risk: "Risk Synthesis (Agent)",
};

export interface IssueResponse {
  reference_id: string;
  verify_url: string;
  qr_data_uri: string;
  issued_at: string;
}

export interface VerifyResponse {
  verified: boolean;
  reference_id: string;
  reason?: string;
  issuer?: string;
  communication_type?: string;
  content?: string;
  content_hash?: string;
  issued_at?: string;
}
