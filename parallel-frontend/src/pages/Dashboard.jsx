import { useEffect, useState, useRef } from "react";
import ChatBubble from "../components/ChatBubble";
import ThemeToggle from "../components/ThemeToggle";
import "./Dashboard.css";
import "../components/ChatPanel.css";

const apiBase = import.meta.env.VITE_API_BASE || "http://localhost:8000";

/** Format E.164 US number so we don't double the country code: 16158066527 -> +1 (615) 806-6527 */
function formatPlivoPhone(num) {
  if (!num) return "";
  const s = String(num).replace(/\D/g, "");
  if (s.length === 11 && s.startsWith("1")) return `+1 (${s.slice(1, 4)}) ${s.slice(4, 7)}-${s.slice(7)}`;
  if (s.length === 10) return `+1 (${s.slice(0, 3)}) ${s.slice(3, 6)}-${s.slice(6)}`;
  return `+${s}`;
}

const MODES = [
  { key: "chat", label: "Chat", icon: "💬", desc: "Talk to your AI agent" },
  { key: "research", label: "Research", icon: "🔍", desc: "AGI web research agent" },
  { key: "action", label: "Action", icon: "⚡", desc: "Composio app actions" },
];

const CONNECT_TOOLKITS = [
  { key: "GMAIL", label: "Gmail" },
  { key: "GOOGLEDOCS", label: "Google Docs" },
  { key: "GOOGLEDRIVE", label: "Google Drive" },
];

export default function Dashboard() {
  const [user, setUser] = useState({ id: null, name: "You" });
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [online, setOnline] = useState([]);
  const [activity, setActivity] = useState([]);
  const [mode, setMode] = useState("chat");
  const [tools, setTools] = useState(null);
  const [composioTools, setComposioTools] = useState([]);
  const [selectedAction, setSelectedAction] = useState("GMAIL_SEND_EMAIL");
  const [composioStatus, setComposioStatus] = useState(null);
  const [connecting, setConnecting] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryEmail, setSummaryEmail] = useState("");
  const [showSummaryForm, setShowSummaryForm] = useState(false);
  const chatEndRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${apiBase}/me`, { credentials: "include" });
        if (res.ok) {
          const data = await res.json();
          setUser({ id: data.id, name: data.name || "You" });
        } else { window.location.reload(); }
      } catch { window.location.reload(); }
    })();
  }, []);

  // Load messages initially, then poll every 5s for new ones (e.g. voice transcripts)
  const refreshMessages = async () => {
    try {
      const res = await fetch(`${apiBase}/messages`, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        setMessages((prev) => {
          // Only update if count changed (avoids scroll jumps)
          if (data.length !== prev.length) return data;
          return prev;
        });
      }
    } catch (e) { console.error(e); }
  };

  useEffect(() => {
    if (!user.id) return;
    refreshMessages();
    const id = setInterval(refreshMessages, 2000);
    return () => clearInterval(id);
  }, [user.id]);

  useEffect(() => {
    if (!user.id) return;
    (async () => {
      try {
        const [toolsRes, cToolsRes, cStatusRes] = await Promise.all([
          fetch(`${apiBase}/tools`, { credentials: "include" }),
          fetch(`${apiBase}/composio/tools`, { credentials: "include" }),
          fetch(`${apiBase}/composio/status`, { credentials: "include" }),
        ]);
        if (toolsRes.ok) setTools(await toolsRes.json());
        if (cToolsRes.ok) {
          const data = await cToolsRes.json();
          setComposioTools(data.toolkits || []);
          if (data.toolkits?.length) setSelectedAction(data.toolkits[0].name);
        }
        if (cStatusRes.ok) setComposioStatus(await cStatusRes.json());
      } catch (e) { console.error(e); }
    })();
  }, [user.id]);

  const refreshTeamActivity = async () => {
    try {
      const [onRes, actRes] = await Promise.all([
        fetch(`${apiBase}/online`, { credentials: "include" }),
        fetch(`${apiBase}/activity`, { credentials: "include" }),
      ]);
      if (onRes.ok) setOnline((await onRes.json()).members || []);
      if (actRes.ok) setActivity((await actRes.json()) || []);
    } catch (e) { console.error(e); }
  };

  useEffect(() => {
    if (!user.id) return;
    refreshTeamActivity();
    const id = setInterval(refreshTeamActivity, 2000);
    return () => clearInterval(id);
  }, [user.id]);

  const sendMessage = async (e) => {
    e?.preventDefault();
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setLoading(true);
    setError("");
    try {
      const body = { content: text, mode };
      if (mode === "action") body.action_tool = selectedAction;
      const res = await fetch(`${apiBase}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Request failed (${res.status})`);
      }
      await res.json();
      const [msgRes, actRes] = await Promise.all([
        fetch(`${apiBase}/messages`, { credentials: "include" }),
        fetch(`${apiBase}/activity`, { credentials: "include" }),
      ]);
      if (msgRes.ok) setMessages(await msgRes.json());
      if (actRes.ok) setActivity(await actRes.json());
    } catch (err) {
      setError(err?.message || "Send failed");
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    try { await fetch(`${apiBase}/auth/logout`, { method: "POST", credentials: "include" }); } catch (_) {}
    window.location.reload();
  };

  const handleConnect = async (toolkit = "GMAIL") => {
    setConnecting(true);
    try {
      const res = await fetch(`${apiBase}/composio/connect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ toolkit }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.redirect_url) window.open(data.redirect_url, "_blank");
      } else {
        const err = await res.json().catch(() => ({}));
        setError(err.detail || "Connection failed");
      }
    } catch (err) {
      setError("Failed to start connection");
    } finally {
      setConnecting(false);
    }
  };

  const refreshComposioStatus = async () => {
    try {
      const res = await fetch(`${apiBase}/composio/status`, { credentials: "include" });
      if (res.ok) setComposioStatus(await res.json());
    } catch (e) { console.error(e); }
  };

  const handleGenerateSummary = async (e) => {
    e?.preventDefault();
    if (!summaryEmail.trim() || summaryLoading) return;
    setSummaryLoading(true);
    setError("");
    try {
      const res = await fetch(`${apiBase}/summary/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email_to: summaryEmail.trim() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Summary generation failed");
      }
      const data = await res.json();
      setShowSummaryForm(false);
      setSummaryEmail("");
      // Refresh messages to show the summary entry
      const [msgRes, actRes] = await Promise.all([
        fetch(`${apiBase}/messages`, { credentials: "include" }),
        fetch(`${apiBase}/activity`, { credentials: "include" }),
      ]);
      if (msgRes.ok) setMessages(await msgRes.json());
      if (actRes.ok) setActivity(await actRes.json());
      const docNote = data.doc_url ? ` Doc: ${data.doc_url}` : "";
      alert(`Summary generated and emailed to ${summaryEmail}!${docNote}`);
    } catch (err) {
      setError(err?.message || "Summary failed");
    } finally {
      setSummaryLoading(false);
    }
  };

  const displayMessages = messages.length
    ? messages
    : [{ id: "welcome", sender_name: "agent", role: "assistant", content: `Hey ${user.name} -- how can I help today?` }];

  const loadingLabel =
    mode === "research" ? "Researching (this can take up to 90s)..." :
    mode === "action" ? "Running action..." : "Thinking...";

  // Clean toolkit names — backend may return "ITEMTOOLKIT(SLUG='GMAIL')" or just "GMAIL"
  const connectedToolkits = (composioStatus?.toolkits || []).map((t) => {
    const s = String(t);
    const m = s.match(/SLUG='([^']+)'/i) || s.match(/SLUG="([^"]+)"/i);
    return m ? m[1].toUpperCase() : s.toUpperCase().trim();
  });

  return (
    <div className="dashboard-simple">
      <header className="dashboard-header">
        <span className="dashboard-user">{user.name}</span>
        <div className="dashboard-actions">
          <button
            type="button"
            className="summary-toggle-btn"
            onClick={() => setShowSummaryForm(!showSummaryForm)}
            title="Generate summary, create Google Doc, and email it"
          >
            Summary + Email
          </button>
          <ThemeToggle />
          <button type="button" className="logout-btn" onClick={handleLogout}>Log out</button>
        </div>
      </header>

      {/* Summary form */}
      {showSummaryForm && (
        <div className="summary-bar">
          <form className="summary-form" onSubmit={handleGenerateSummary}>
            <span className="summary-label">Generate chat summary, save to Google Doc, and email to:</span>
            <input
              className="summary-email-input"
              type="email"
              placeholder="recipient@example.com"
              value={summaryEmail}
              onChange={(e) => setSummaryEmail(e.target.value)}
              disabled={summaryLoading}
              required
            />
            <button type="submit" className="summary-send-btn" disabled={summaryLoading || !summaryEmail.trim()}>
              {summaryLoading ? "Generating..." : "Generate & Send"}
            </button>
            <button type="button" className="summary-cancel-btn" onClick={() => setShowSummaryForm(false)}>Cancel</button>
          </form>
        </div>
      )}

      <div className="dashboard-panels">
        {/* ── left: chat ── */}
        <div className="chat-wrapper glass chat-panel">
          <div className="mode-bar">
            {MODES.map((m) => (
              <button
                key={m.key}
                className={`mode-btn ${mode === m.key ? "active" : ""}`}
                onClick={() => setMode(m.key)}
                title={m.desc}
              >
                <span className="mode-icon">{m.icon}</span> {m.label}
              </button>
            ))}
            {mode === "action" && composioTools.length > 0 && (
              <select
                className="toolkit-select"
                value={selectedAction}
                onChange={(e) => setSelectedAction(e.target.value)}
              >
                {composioTools.map((t) => (
                  <option key={t.name} value={t.name}>{t.label}</option>
                ))}
              </select>
            )}
          </div>

          {mode === "research" && (
            <div className="mode-info research-info">
              AGI browser agent will research the web for you. Queries take 30-90 seconds.
            </div>
          )}
          {mode === "action" && (
            <div className="mode-info action-info">
              Composio executes real actions in apps.
              {composioStatus && !composioStatus.connected && (
                <span> You need to connect your accounts below first.</span>
              )}
              {composioStatus?.connected && (
                <span> Connected: {connectedToolkits.join(", ") || "ready"}</span>
              )}
            </div>
          )}

          <div className="chat-scroll">
            {displayMessages.map((m) => (
              <ChatBubble key={m.id} sender={m.role === "user" ? "user" : "ai"} text={m.content} />
            ))}
            {error && <div className="status-bubble error">{error}</div>}
            {loading && (
              <div className="status-bubble">
                <span>{loadingLabel}</span>
                <span className="status-dots"><span></span><span></span><span></span></span>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          <form className="input-container" onSubmit={sendMessage}>
            <input
              className="chat-input"
              placeholder={
                mode === "research" ? "What should AGI research?" :
                mode === "action" ? `Describe the action (e.g. "Send email to ...")` :
                "Ask your agent..."
              }
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={loading}
            />
            <button type="submit" className="chat-send" disabled={loading}>
              {mode === "research" ? "Research" : mode === "action" ? "Run" : "Send"}
            </button>
          </form>
        </div>

        {/* ── right: sidebar ── */}
        <aside className="activity-panel glass">
          {tools && (
            <div className="tools-status">
              <h3 className="activity-title">Sponsor Tools</h3>
              <div className="tool-cards">
                <div className={`tool-card ${tools.agi?.enabled ? "enabled" : "disabled"}`}>
                  <span className="tool-indicator" />
                  <div>
                    <strong>AGI Research</strong>
                    <p>{tools.agi?.enabled ? "Connected (REST API)" : "No API key"}</p>
                  </div>
                </div>
                <div className={`tool-card ${tools.composio?.enabled ? "enabled" : "disabled"}`}>
                  <span className="tool-indicator" />
                  <div>
                    <strong>Composio Actions</strong>
                    <p>
                      {tools.composio?.enabled
                        ? composioStatus?.connected
                          ? `Connected (${connectedToolkits.join(", ") || "active"})`
                          : "API key set - connect accounts below"
                        : "No API key"}
                    </p>
                    {tools.composio?.enabled && (
                      <div className="connect-buttons">
                        {CONNECT_TOOLKITS.map((tk) => (
                          <button
                            key={tk.key}
                            className={`connect-btn ${connectedToolkits.includes(tk.key) ? "connected" : ""}`}
                            onClick={() => handleConnect(tk.key)}
                            disabled={connecting}
                          >
                            {connectedToolkits.includes(tk.key) ? `${tk.label} ✓` : `Connect ${tk.label}`}
                          </button>
                        ))}
                        <button className="connect-btn refresh-status-btn" onClick={refreshComposioStatus}>
                          Refresh Status
                        </button>
                      </div>
                    )}
                  </div>
                </div>
                <div className={`tool-card ${tools.plivo?.enabled ? "enabled" : "disabled"}`}>
                  <span className="tool-indicator" />
                  <div>
                    <strong>Plivo Voice/SMS</strong>
                    <p>
                      {tools.plivo?.enabled
                        ? <>Call: <span className="phone-number">{formatPlivoPhone(tools.plivo.phone_number)}</span></>
                        : "Not configured"}
                    </p>
                    {tools.plivo?.voice_mode === "live" && (
                      <p className="voice-mode-badge live">Live AI Agent (Gemini)</p>
                    )}
                    {tools.plivo?.voice_mode === "record" && tools.plivo?.enabled && (
                      <p className="voice-mode-badge record">Record &amp; Transcribe</p>
                    )}
                    {tools.tunnel_url && (
                      <p className="tunnel-row">
                        <a href={tools.tunnel_url} target="_blank" rel="noopener noreferrer" className="tunnel-link">
                          Test tunnel
                        </a>
                      </p>
                    )}
                  </div>
                </div>
                {tools.gemini_voice && (
                  <div className={`tool-card ${tools.gemini_voice?.enabled ? "enabled" : "disabled"}`}>
                    <span className="tool-indicator" />
                    <div>
                      <strong>Gemini Voice AI</strong>
                      <p>{tools.gemini_voice?.enabled ? "Pipecat + Gemini Live (speech-to-speech)" : "No Gemini API key"}</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="activity-header">
            <h3 className="activity-title">Team Activity</h3>
            <button type="button" className="activity-refresh-btn" onClick={refreshTeamActivity}>Refresh</button>
          </div>
          <div className="online-row">
            {online.map((m) => (
              <div key={m.id} className="online-member">
                <span className={`online-dot ${m.online ? "online" : "offline"}`} />
                <span>{m.name}</span>
              </div>
            ))}
          </div>
          <div className="activity-feed">
            {activity.length === 0 && (
              <p className="activity-empty">No activity yet. Send a message to see updates here.</p>
            )}
            {activity.map((a) => (
              <div key={a.id} className="activity-item">
                <span className="activity-name">{a.user_name}:</span>{" "}
                <span className="activity-summary">{a.summary}</span>
              </div>
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}
