// src/components/SummaryPanel.jsx
import { useEffect, useState, useMemo } from "react";
import "./SummaryPanel.css";

const statusMap = {
  Chat: { label: "In chat", detail: "Responding to workspace asks." },
  Team: { label: "Team activity", detail: "Watching live team updates." },
  Inbox: { label: "Inbox review", detail: "Triaging routed tasks." },
  IDE: { label: "Development", detail: "Editing code in IDE mode." },
};

export default function SummaryPanel({
  user = { id: "you", name: "You" },
  activeTool = "Chat",
}) {
  const [activityLog, setActivityLog] = useState([]);

  const apiBase = import.meta.env.VITE_API_BASE || "http://localhost:8000";
  const status = statusMap[activeTool] || statusMap.Chat;

  // ----------------------------------------
  // Poll backend /team/activity -> activityLog
  // ----------------------------------------
  useEffect(() => {
    let cancelled = false;

    const fetchActivity = async () => {
      try {
        const res = await fetch(`${apiBase}/team/activity`, {
          credentials: "include",
        });
        if (!res.ok) {
          console.error("team/activity failed", res.status);
          return;
        }
        const data = await res.json();
        const members = data.members || [];

        // Flatten members -> activity entries
        const events = members
          .filter((m) => m.last_activity)
          .map((m) => {
            const at = m.last_activity.at
              ? new Date(m.last_activity.at)
              : null;

            return {
              id: `${m.id}-${m.last_activity.at || ""}`, // unique key
              userId: m.id,
              name: m.name,
              role: m.role,
              state: m.last_activity.room_name || "Active",
              detail: m.last_activity.message || "",
              at,
              atLabel: at
                ? at.toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })
                : "",
            };
          })
          .sort((a, b) => (b.at?.getTime() || 0) - (a.at?.getTime() || 0));

        if (!cancelled) {
          setActivityLog(events);
        }
      } catch (err) {
        console.error("team/activity error", err);
      }
    };

    fetchActivity();
    const id = setInterval(fetchActivity, 1000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [apiBase]);

  // ----------------------------------------
  // Fallback activity if nothing from backend
  // ----------------------------------------
  const effectiveActivity = useMemo(() => {
    if (activityLog.length > 0) return activityLog;
    return [
      {
        id: user.id || "you",
        userId: user.id || "you",
        name: user.name || "You",
        state: status.label,
        detail: status.detail,
        at: null,
        atLabel: "",
      },
    ];
  }, [activityLog, user, status]);

  // Current status per person (top section)
  const current = useMemo(() => {
    const byName = {};
    for (const entry of effectiveActivity) {
      const existing = byName[entry.name];
      if (!existing) {
        byName[entry.name] = entry;
      } else if (
        entry.at &&
        (!existing.at || entry.at.getTime() > existing.at.getTime())
      ) {
        byName[entry.name] = entry;
      }
    }
    return Object.values(byName);
  }, [effectiveActivity]);

  return (
    <aside className="summary-panel glass">
      <div className="summary-header">
        <div>
          <h2 className="summary-title">Activity</h2>
          <p className="summary-subtitle">
            Signed in as {user.name || "You"}
          </p>
        </div>
        <span className="summary-chip">{status.label}</span>
      </div>

      {/* Top: current status per teammate */}
      <div className="summary-list">
        {current.map((item) => (
          <div className="file-block" key={item.userId || item.id}>
            <div className="file-row">
              <div className="file-name">{item.name}</div>
              <div className="file-tag">{item.state}</div>
            </div>
            <pre className="code-box">
              {item.detail}
              {item.atLabel ? ` — ${item.atLabel}` : ""}
            </pre>
          </div>
        ))}
      </div>

      {/* Below: scrolling activity feed */}
      <div className="activity-feed">
        {effectiveActivity.map((item) => (
          <div className="activity-line" key={item.id}>
            [{item.atLabel || "--:--"}] {item.name}: {item.detail}
          </div>
        ))}
      </div>
    </aside>
  );
}
