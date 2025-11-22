// src/components/CommandBar.jsx
export default function CommandBar() {
  return (
    <div
      style={{
        width: "100%",
        padding: "22px",
        background: "rgba(10,10,15,0.55)",
        borderTop: "1px solid rgba(255,255,255,0.08)",
        backdropFilter: "blur(18px)",
        display: "flex",
        gap: "14px",
        position: "absolute",
        bottom: 0,
      }}
    >
      <input
        placeholder="Ask AI…"
        style={{
          flex: 1,
          padding: "18px",
          borderRadius: "16px",
          border: "none",
          background: "rgba(255,255,255,0.06)",
          color: "white",
          outline: "none",
          fontSize: "17px",
        }}
      />

      <button
        style={{
          padding: "16px 36px",
          borderRadius: "16px",
          border: "none",
          background:
            "linear-gradient(135deg,#7c3aed,#6366f1)",
          color: "white",
          cursor: "pointer",
          fontSize: "18px",
          boxShadow: "0 0 20px rgba(120,80,255,0.6)",
        }}
      >
        Run
      </button>
    </div>
  );
}
