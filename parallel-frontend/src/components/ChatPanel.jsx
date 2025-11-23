import { useState, useEffect, useMemo } from "react";
import "./ChatPanel.css";
import ChatBubble from "./ChatBubble";

export default function ChatPanel() {
  const [messages, setMessages] = useState([
    { sender: "ai", text: "Hey Yug — how can I help today?" }
  ]);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const [status, setStatus] = useState("");
  const [roomId, setRoomId] = useState(null);
  const [roomError, setRoomError] = useState("");

  const apiBase = import.meta.env.VITE_API_BASE || "http://localhost:8000";

  async function ensureRoom() {
    if (roomId || roomError) return roomId;
    try {
      const res = await fetch(`${apiBase}/rooms`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ room_name: "Parallel Demo" }),
      });
      if (!res.ok) throw new Error(`Room creation failed (${res.status})`);
      const data = await res.json();
      setRoomId(data.room_id);
      return data.room_id;
    } catch (err) {
      const msg = err?.message || "Failed to create room";
      setRoomError(msg);
      setStatus(msg);
      return null;
    }
  }

  async function send() {
    if (!input.trim()) return;
    const room = roomId || (await ensureRoom());
    if (!room) return;

    const userMessage = { sender: "user", text: input };
    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setTyping(true);

    try {
      setStatus("Sending to backend...");
      const res = await fetch(`${apiBase}/rooms/${room}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "demo-user",
          user_name: "Demo User",
          content: userMessage.text,
          mode: "team",
        }),
      });

      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        const msg = detail?.detail || `Request failed (${res.status})`;
        throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
      }

      const data = await res.json();
      const serverMessages = (data.messages || []).map((m) => ({
        sender: m.sender_name || m.sender_id || "agent",
        text: m.content,
        role: m.role,
      }));
      // Prefer coordinator / final assistant only
      const coordinator = [...serverMessages].reverse().find((m) =>
        (m.sender || "").toLowerCase().includes("coordinator")
      );
      const lastAssistant = [...serverMessages].reverse().find((m) => m.role === "assistant");
      const assistantMsg = coordinator || lastAssistant;

      setMessages((prev) => [
        ...prev,
        assistantMsg || { sender: "agent", text: "Got it.", role: "assistant" },
      ]);
      setStatus("");
    } catch (err) {
      setStatus(`Error: ${err?.message || "Request failed"}`);
      setMessages(prev => [...prev, { sender: "ai", text: "Something went wrong. Try again." }]);
    } finally {
      setTyping(false);
    }
  }

  const formatStatus = useMemo(() => ({
    ask_received: ({ meta }) => `Ask received (${meta?.mode || "team"})`,
    routing_agent: ({ meta }) => `Routing to ${meta?.agent || "agent"}`,
    agent_reply: ({ meta }) => `Reply from ${meta?.agent || "agent"}`,
    team_fanout_start: () => "Querying teammates...",
    synthesizing: () => "Synthesizing drafts...",
    synthesis_complete: () => "Synthesis complete",
  }), []);

  useEffect(() => {
    const base = import.meta.env.VITE_API_BASE || "http://localhost:8000";
    const source = new EventSource(`${base}/events`);

    source.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "status") {
          const formatter = formatStatus[data.step];
          const text = formatter ? formatter(data) : data.step;
          setStatus(text);
        } else if (data.type === "error") {
          setStatus(`Error: ${data.message}`);
        }
      } catch (err) {
        console.error("Error parsing event", err);
      }
    };

    source.onerror = () => {
      setStatus("Disconnected from backend");
    };

    return () => source.close();
  }, [formatStatus]);

  const handleSubmit = (e) => {
    e.preventDefault();
    send();
  };

  return (
    <div className="chat-wrapper glass">
      <div className="chat-scroll">
        {messages.map((m, i) => (
          <ChatBubble key={i} sender={m.sender} text={m.text} />
        ))}
        {status && (
          <div className="status-bubble">
            <span>{status}</span>
            <span className="status-dots">
              <span></span>
              <span></span>
              <span></span>
            </span>
          </div>
        )}
      </div>

      <form className="input-container" onSubmit={handleSubmit}>
        <input
          className="chat-input"
          placeholder="Ask Parallel OS..."
          value={input}
          onChange={e => setInput(e.target.value)}
        />
        <button type="submit" className="chat-send">Send</button>
      </form>
    </div>
  );
}
