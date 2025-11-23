import ThemeToggle from "./ThemeToggle";
import logo from "../assets/parallel-logo.svg";
import "./Sidebar.css";

export default function Sidebar({ active = "Team", onSelect = () => {}, onToggle = () => {} }) {
  const navItems = [
    { label: "Team" },
    { label: "Inbox" },
    { label: "IDE" },
  ];

  const chats = [
    { id: "c1", title: "Plan next sprint" },
    { id: "c2", title: "Routing bugfix" },
    { id: "c3", title: "UI polish tasks" },
    { id: "c4", title: "Demo prep" },
  ];

  return (
    <div className="sidebar glass">
      <div className="sidebar-top">
        <div className="sidebar-header">
          <button
            className="logo-button"
            aria-label="New chat"
            onClick={() => onSelect("Chat")}
          >
            <img src={logo} alt="Parallel Logo" className="sidebar-logo" />
          </button>
        </div>

        <div className="nav-list">
          {navItems.map((item) => (
            <button
              key={item.label}
              className={`sidebar-btn ghost ${active === item.label ? "active" : ""}`}
              onClick={() => onSelect(item.label)}
            >
              {item.label}
            </button>
          ))}
        </div>

        <div className="chat-list">
          <div className="section-label">Recent chats</div>
          <div className="chat-items">
            {chats.map((chat) => (
              <button
                key={chat.id}
                className="chat-item"
                type="button"
                onClick={() => onSelect("Chat")}
              >
                <span className="chat-title">{chat.title}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="sidebar-bottom">
        <ThemeToggle />
        <button className="sidebar-btn ghost collapse" onClick={onToggle}>Collapse</button>
      </div>
    </div>
  );
}
