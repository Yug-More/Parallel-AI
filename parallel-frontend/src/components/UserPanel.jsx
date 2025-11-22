// src/components/UserPanel.jsx
import { motion } from "framer-motion";

export default function UserPanel({ name, isSelf }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 25, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.45 }}
      className="glass"
      style={{
        padding: "22px",
        height: "420px",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div style={{ marginBottom: "10px", fontSize: "22px", fontWeight: 600 }}>
        {name} {isSelf && <span style={{ color: "#a78bfa" }}>(You)</span>}
      </div>

      <div
        style={{
          flex: 1,
          background: "rgba(255,255,255,0.04)",
          borderRadius: "14px",
          padding: "18px",
          overflowY: "auto",
          border: "1px solid rgba(255,255,255,0.05)",
        }}
      >
        AI output will appear here…
      </div>
    </motion.div>
  );
}
