// src/components/CollabDrawer.jsx
export default function CollabDrawer() {
  return (
    <div
      style={{
        position: "absolute",
        right: 0,
        top: "60px",
        width: "320px",
        height: "calc(100% - 120px)",
        background: "rgba(255,255,255,0.05)",
        borderLeft: "1px solid rgba(255,255,255,0.1)",
        backdropFilter: "blur(16px)",
        padding: "22px",
      }}
    >
      <h3 style={{ marginBottom: "10px", fontSize: "20px" }}>Shared Notes</h3>
      <textarea
        style={{
          width: "100%",
          height: "88%",
          borderRadius: "16px",
          padding: "16px",
          background: "rgba(255,255,255,0.07)",
          border: "none",
          color: "white",
          outline: "none",
        }}
        placeholder="Team notes…"
      />
    </div>
  );
}
