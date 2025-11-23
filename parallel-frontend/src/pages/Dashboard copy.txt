import { useEffect, useState } from "react";
import "./Dashboard.css";
import Sidebar from "../components/Sidebar";
import ChatPanel from "../components/ChatPanel";
import SummaryPanel from "../components/SummaryPanel";
import TeamPanel from "../components/TeamPanel";
import { GitTextEditorPanel } from "../features/ide/GitTextEditorPanel";
import Manager from "./Manager";
import NotificationsPanel from "../components/NotificationsPanel";

function TeamView({ user, statuses }) {
  return (
    <div className="chat-wrapper glass">
      <div className="panel-head">
        <div>
          <p className="eyebrow">Live work</p>
          <h2>Team activity</h2>
        </div>
      </div>
      <TeamPanel user={user} statuses={statuses} />
      <p className="subhead">Updates stream here when Team is selected.</p>
    </div>
  );
}

function InboxView({ inbox }) {
  return (
    <div className="chat-wrapper glass">
      <div className="panel-head">
        <div>
          <p className="eyebrow">Inbox</p>
          <h2>Captured tasks</h2>
        </div>
      </div>
      {inbox.length === 0 && <p className="subhead">No tasks yet.</p>}
      <div className="inbox-list">
        {inbox.map((task) => (
          <div className="inbox-item" key={task.id}>
            <div className="inbox-title">{task.content}</div>
            <div className="inbox-meta">
              <span>{task.status}</span>
              {task.priority && <span>{task.priority}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function IdeView() {
  return <GitTextEditorPanel />;
}

export default function Dashboard() {
  const [activeTool, setActiveTool] = useState("Team");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [user, setUser] = useState({ id: "demo-user", name: "You" });
  const [activityLog, setActivityLog] = useState([]);
  const [teamStatuses, setTeamStatuses] = useState([]);
  const [roomId, setRoomId] = useState(null);
  const [roomData, setRoomData] = useState(null);
  const [inbox, setInbox] = useState([]);
  const apiBase = import.meta.env.VITE_API_BASE || "http://localhost:8000";

  useEffect(() => {
    const fetchMe = async () => {
      try {
        const res = await fetch(`${apiBase}/me`, { credentials: "include" });
        if (res.ok) {
          const data = await res.json();
          setUser({ id: data.id, name: data.name || "You" });
        }
      } catch (err) {
        // ignore; keep default
      }
    };
    fetchMe();
  }, [apiBase]);

  useEffect(() => {
    const label = activeTool === "IDE" ? "Development" : activeTool === "Inbox" ? "Inbox review" : activeTool === "Team" ? "Team activity" : "In chat";
    const entry = {
      id: `${Date.now()}`,
      state: label,
      detail: `Switched to ${activeTool}`,
      at: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      name: user.name || "You",
    };
    setActivityLog((prev) => [entry, ...prev].slice(0, 6));
    setTeamStatuses([
      { name: user.name || "You", role: label, state: "active" },
    ]);
  }, [activeTool, user.name]);

  useEffect(() => {
    if (!roomId) return;
    const fetchRoom = async () => {
      try {
        const res = await fetch(`${apiBase}/rooms/${roomId}`, { credentials: "include" });
        if (res.ok) {
          const data = await res.json();
          setRoomData(data);
        }
      } catch (err) {
        // ignore
      }
    };
    fetchRoom();
    const id = setInterval(fetchRoom, 5000);
    return () => clearInterval(id);
  }, [roomId, apiBase]);

  useEffect(() => {
    if (!user.id) return;
    const fetchInbox = async () => {
      try {
        const res = await fetch(`${apiBase}/users/${user.id}/inbox`, { credentials: "include" });
        if (res.ok) {
          const data = await res.json();
          setInbox(data || []);
        }
      } catch (err) {
        // ignore
      }
    };
    fetchInbox();
    const id = setInterval(fetchInbox, 7000);
    return () => clearInterval(id);
  }, [user.id, apiBase]);

  const handleLogout = async () => {
    try {
      await fetch(`${apiBase}/auth/logout`, { method: "POST", credentials: "include" });
    } catch (err) {
      // ignore
    } finally {
      window.location.reload();
    }
  };

  const renderRight = () => {
  if (activeTool === "Manager") return <Manager currentUser={user} />;
    if (activeTool === "Team") return (
      <>
        <TeamView user={user} statuses={teamStatuses} />
        <NotificationsPanel user={user} />
      </>
    );
    if (activeTool === "Inbox") return <InboxView inbox={inbox} />;
    if (activeTool === "IDE") return <IdeView />;
    return <SummaryPanel user={user} activeTool={activeTool} activityLog={activityLog} roomData={roomData} />;
  };

  const containerClass = sidebarOpen ? "dashboard-container" : "dashboard-container collapsed";

  return (
   <div className={containerClass}>
  {sidebarOpen ? (
    <Sidebar
      active={activeTool}
      onSelect={setActiveTool}
      onToggle={() => setSidebarOpen(false)}
      onLogout={handleLogout}
    />
  ) : (
    <div className="sidebar-toggle-shell">
      <button className="sidebar-toggle" onClick={() => setSidebarOpen(true)} aria-label="Expand sidebar">
        ‹›
      </button>
    </div>
  )}

  {/* 👇 Hide Chat and Right Panel when Manager is active */}
  {activeTool === "Manager" ? (
    <div style={{ gridColumn: "span 2", width: "100%" }}>
      <Manager currentUser={user} />
    </div>
  ) : (
    <>
      <ChatPanel user={user} onRoomReady={setRoomId} />
      {renderRight()}
    </>
  )}
</div>
  );
}
