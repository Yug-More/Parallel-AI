import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ThemeProvider } from "./context/ThemeContext";
import Landing from "./pages/Landing";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";
import Signup from "./pages/Signup";

export default function App() {
  const [page, setPage] = useState("landing");

  function go(to) {
    setPage(to);
  }

  return (
    <ThemeProvider>
      <AnimatePresence mode="wait">
        <motion.div
          key={page}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -12 }}
          transition={{ duration: 0.28 }}
          style={{ height: "100%" }}
        >
          {page === "landing" && <Landing goLogin={() => go("login")} />}
          {page === "login" && (
            <Login
              goDashboard={() => go("dashboard")}
              goSignup={() => go("signup")}
              goForgot={() => {}}
            />
          )}
          {page === "signup" && (
            <Signup goLogin={() => go("login")} goDashboard={() => go("dashboard")} />
          )}
          {page === "dashboard" && <Dashboard />}
        </motion.div>
      </AnimatePresence>
    </ThemeProvider>
  );
}
