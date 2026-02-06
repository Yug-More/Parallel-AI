import { useEffect, useState } from "react";
import ChatBubble from "../components/ChatBubble";
import ThemeToggle from "../components/ThemeToggle";
import "./Dashboard.css";
import "../components/ChatPanel.css";

const apiBase = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export default function Dashboard() {
  const [user, setUser] = useState({ id: null, name: "You" });
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [online, setOnline] = useState([]);
  const [activity, setActivity] = useState([]);

  // Auth: fetch current user
  useEffect(() => {
    const fetchMe = async () => {
      try {
        const res = await fetch(`${apiBase}/me`, { credentials: "include" });
        if (res.ok) {
          const data = await res.json();
          setUser({ id: data.id, name: data.name || "You" });
        } else {
          window.location.reload();
        }
      } catch {
        window.location.reload();
      }
    };
    fetchMe();
  }, []);

  // Messages for current user
  useEffect(() => {
    if (!user.id) return;
    const fetchMessages = async () => {
      try {
        const res = await fetch(`${apiBase}/messages`, { credentials: "include" });
        if (res.ok) {
          const data = await res.json();
          setMessages(data || []);
        }
      } catch (e) {
        console.error(e);
      }
    };
    fetchMessages();
  }, [user.id]);

  const refreshTeamActivity = async () => {
    try {
      const [onRes, actRes] = await Promise.all([
        fetch(`${apiBase}/online`, { credentials: "include" }),
        fetch(`${apiBase}/activity`, { credentials: "include" }),
      ]);
      if (onRes.ok) {
        const data = await onRes.json();
        setOnline(data.members || []);
      }
      if (actRes.ok) {
        const data = await actRes.json();
        setActivity(data || []);
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Online members + activity feed (poll every 2s for real-time updates)
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
      const res = await fetch(`${apiBase}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ content: text }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Request failed (${res.status})`);
      }
      await res.json();
      // Refetch messages and activity so UI is in sync
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
    try {
      await fetch(`${apiBase}/auth/logout`, { method: "POST", credentials: "include" });
    } catch (_) {}
    window.location.reload();
  };

  const displayMessages = messages.length
    ? messages
    : [{ sender_name: "agent", role: "assistant", content: `Hey ${user.name} — how can I help today?` }];

  return (
    <div className="dashboard-simple">
      <header className="dashboard-header">
        <span className="dashboard-user">{user.name}</span>
        <div className="dashboard-actions">
          <ThemeToggle />
          <button type="button" className="logout-btn" onClick={handleLogout}>
            Log out
          </button>
        </div>
      </header>

      <div className="dashboard-panels">
        <div className="chat-wrapper glass chat-panel">
          <div className="chat-scroll">
            {displayMessages.map((m) => (
              <ChatBubble
                key={m.id}
                sender={m.role === "user" ? "user" : "ai"}
                text={m.content}
              />
            ))}
            {error && <div className="status-bubble error">{error}</div>}
            {loading && (
              <div className="status-bubble">
                <span>Thinking...</span>
                <span className="status-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </span>
              </div>
            )}
          </div>
          <form className="input-container" onSubmit={sendMessage}>
            <input
              className="chat-input"
              placeholder="Ask your agent..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={loading}
            />
            <button type="submit" className="chat-send" disabled={loading}>
              Send
            </button>
          </form>
        </div>

        <aside className="activity-panel glass">
          <div className="activity-header">
            <h3 className="activity-title">Team activity</h3>
            <button
              type="button"
              className="activity-refresh-btn"
              onClick={refreshTeamActivity}
              title="Refresh"
              aria-label="Refresh team activity"
            >
              Refresh
            </button>
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
