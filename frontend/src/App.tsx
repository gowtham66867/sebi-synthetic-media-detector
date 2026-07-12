import { useState } from "react";
import "./App.css";
import MediaAnalysis from "./MediaAnalysis";
import PhishingAnalysis from "./PhishingAnalysis";
import IssueCommunication from "./IssueCommunication";
import VerifyCommunication from "./VerifyCommunication";

type Tab = "clip" | "message" | "issue" | "verify";

function App() {
  const verifyMatch = window.location.pathname.match(/^\/verify\/([^/]+)/);
  const [tab, setTab] = useState<Tab>(verifyMatch ? "verify" : "clip");

  return (
    <div className="page">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">SM</span>
          <div>
            <h1>AI-Driven Detection of Synthetic Media &amp; Phishing Attacks</h1>
            <p className="subtitle">SEBI Securities Market TechSprint — Dual Protection Framework</p>
          </div>
        </div>
      </header>

      <nav className="tab-row">
        <button className={`tab-btn ${tab === "clip" ? "active" : ""}`} onClick={() => setTab("clip")}>
          Suspect Clip
        </button>
        <button className={`tab-btn ${tab === "message" ? "active" : ""}`} onClick={() => setTab("message")}>
          Suspicious Message
        </button>
        <button className={`tab-btn ${tab === "issue" ? "active" : ""}`} onClick={() => setTab("issue")}>
          Issue Communication
        </button>
        <button className={`tab-btn ${tab === "verify" ? "active" : ""}`} onClick={() => setTab("verify")}>
          Verify Communication
        </button>
      </nav>

      <main className="content">
        {tab === "clip" && <MediaAnalysis />}
        {tab === "message" && <PhishingAnalysis />}
        {tab === "issue" && <IssueCommunication />}
        {tab === "verify" && <VerifyCommunication initialReferenceId={verifyMatch?.[1]} />}
      </main>
    </div>
  );
}

export default App;
