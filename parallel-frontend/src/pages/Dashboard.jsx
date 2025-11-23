import { useState } from "react";
import "./Dashboard.css";
import Sidebar from "../components/Sidebar";
import ChatPanel from "../components/ChatPanel";
import SummaryPanel from "../components/SummaryPanel";
import TeamPanel from "../components/TeamPanel";

function TeamView() {
  return (
    <div className="chat-wrapper glass">
      <div className="panel-head">
        <div>
          <p className="eyebrow">Live work</p>
          <h2>Team activity</h2>
        </div>
      </div>
      <TeamPanel />
      <p className="subhead">Updates stream here when Team is selected.</p>
    </div>
  );
}

function InboxView() {
  return (
    <div className="chat-wrapper glass">
      <div className="panel-head">
        <div>
          <p className="eyebrow">Inbox</p>
          <h2>Captured tasks</h2>
        </div>
      </div>
      <p className="subhead">Tasks routed from chat will show here.</p>
    </div>
  );
}

function IdeView() {
  return (
    <div className="chat-wrapper glass">
      <div className="panel-head">
        <div>
          <p className="eyebrow">IDE</p>
          <h2>Coming soon</h2>
        </div>
      </div>
      <p className="subhead">Reserved for future embedded coder.</p>
    </div>
  );
}

export default function Dashboard() {
  const [activeTool, setActiveTool] = useState("Chat");

  const renderCenter = () => {
    if (activeTool === "Team") return <TeamView />;
    if (activeTool === "Inbox") return <InboxView />;
    if (activeTool === "IDE") return <IdeView />;
    return <ChatPanel />;
  };

  return (
    <div className="dashboard-container">
      <Sidebar active={activeTool} onSelect={setActiveTool} />
      {renderCenter()}
      <SummaryPanel />
    </div>
  );
}
