// src/components/ThemeToggle.jsx
import { useState } from "react";

export default function ThemeToggle() {
  const [mode, setMode] = useState("dark");

  const toggle = () => {
    const next = mode === "dark" ? "neon" : "dark";
    setMode(next);

    if (next === "dark") {
      document.body.style.background = "#030303";
      document.body.style.color = "white";
    } else {
      document.body.style.background =
        "radial-gradient(circle at 20% 20%, #6d28d9, #4f46e5, #0ea5e9)";
      document.body.style.color = "white";
    }
  };

  return (
    <button
      onClick={toggle}
      style={{
        position: "fixed",
        top: "20px",
        right: "20px",
        padding: "14px 20px",
        borderRadius: "14px",
        background: "linear-gradient(145deg,#4f46e5,#7c3aed)",
        border: "none",
        color: "white",
        cursor: "pointer",
        zIndex: 1000,
        boxShadow: "0 0 20px rgba(80,40,255,0.6)",
      }}
    >
      Theme
    </button>
  );
}
