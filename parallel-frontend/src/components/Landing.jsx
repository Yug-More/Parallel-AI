import { motion } from "framer-motion";
import Background3D from "./Background3D";

export default function Landing({ onEnter }) {
  return (
    <div
      style={{
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        padding: "24px",
        position: "relative",
      }}
    >
      <Background3D />

      <motion.h1
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 1 }}
        style={{
          fontSize: "70px",
          fontWeight: 900,
          letterSpacing: "-1px",
          maxWidth: "1000px",
          textShadow: "0 0 50px rgba(140,80,255,0.5)",
        }}
      >
        Parallel
      </motion.h1>

      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4, duration: 1 }}
        style={{
          fontSize: "22px",
          color: "#aaa",
          marginTop: "16px",
          maxWidth: "800px",
        }}
      >
        Step into the <span className="highlight">Multiplayer AI Dimension.</span>
        <br />
        Build, chat, think & collaborate with teammates:
        <b> Yug • Severin • Sean • Nayab</b>.
      </motion.p>

      <motion.button
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ delay: 0.8 }}
        onClick={onEnter}
        style={{
          marginTop: "45px",
          padding: "22px 60px",
          fontSize: "24px",
          background: "linear-gradient(135deg, #7c3aed, #6366f1)",
          border: "none",
          borderRadius: "18px",
          cursor: "pointer",
          color: "white",
          fontWeight: 700,
          boxShadow: "0 0 30px rgba(100,60,255,0.6)",
        }}
      >
        Enter Workspace →
      </motion.button>
    </div>
  );
}
