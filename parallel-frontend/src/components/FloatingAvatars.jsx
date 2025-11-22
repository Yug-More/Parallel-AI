// src/components/FloatingAvatars.jsx
import { motion } from "framer-motion";

export default function FloatingAvatars() {
  const users = ["Yug", "Severin", "Sean", "Nayab"];

  return (
    <div style={{ display: "flex", gap: "18px", padding: "18px" }}>
      {users.map((user, i) => (
        <motion.div
          key={user}
          initial={{ y: -20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: i * 0.18, type: "spring", stiffness: 140 }}
          style={{
            width: "60px",
            height: "60px",
            borderRadius: "50%",
            background:
              "radial-gradient(circle, #8b5cf6, #6d28d9)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "white",
            fontWeight: 700,
            fontSize: "20px",
            boxShadow: "0 0 25px rgba(140,80,255,0.7)",
          }}
        >
          {user[0]}
        </motion.div>
      ))}
    </div>
  );
}
