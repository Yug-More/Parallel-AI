// src/components/Sidebar.jsx
export default function Sidebar() {
  return (
    <div
      style={{
        width: "90px",
        background: "rgba(25, 25, 35, 0.40)",
        backdropFilter: "blur(18px)",
        borderRight: "1px solid rgba(255,255,255,0.08)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        paddingTop: "20px",
        gap: "38px",
        zIndex: 10,
        boxShadow: "0 0 30px rgba(100,60,255,0.25)",
      }}
    >
      <div style={{ fontSize: "34px" }}>⚡</div>

      {["🏠", "💬", "🧠", "⚙️"].map((icon) => (
        <button
          key={icon}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            fontSize: "28px",
            color: "#9e9eab",
            transition: "0.2s",
          }}
          onMouseEnter={(e) => (e.target.style.scale = "1.3")}
          onMouseLeave={(e) => (e.target.style.scale = "1.0")}
        >
          {icon}
        </button>
      ))}
    </div>
  );
}
