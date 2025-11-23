import { useState } from "react";
import { motion } from "framer-motion";
import "./Auth.css";

export default function Login({ goSignup, goForgot, goDashboard }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);

  const apiBase = import.meta.env.VITE_API_BASE || "http://localhost:8000";

  const submit = async () => {
    if (!email || !password) {
      setStatus("Enter email and password.");
      return;
    }
    setLoading(true);
    setStatus("");
    try {
      console.log("Login: sending request", { apiBase, email });
      const res = await fetch(`${apiBase}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const text = await res.text();
        console.error("Login failed", res.status, text);
        setStatus(`Invalid credentials (${res.status}).`);
        return;
      }

      // Immediately confirm cookie works by hitting /me
      try {
        const meRes = await fetch(`${apiBase}/me`, {
          credentials: "include",
        });
        if (meRes.ok) {
          const me = await meRes.json();
          console.log("Logged in as", me);
          setStatus(`Signed in as ${me.name || me.email}.`);
        } else {
          console.warn("Login succeeded but /me failed", meRes.status);
          setStatus("Signed in, but failed to load your profile.");
        }
      } catch (err) {
        console.warn("Error fetching /me after login", err);
      }

      goDashboard();
    } catch (err) {
      console.error("Login error", err);
      setStatus("Login failed. See console.");
    } finally {
      setLoading(false);
    }
  };

  const onKey = (e) => {
    if (e.key === "Enter") submit();
  };

  return (
    <div className="auth-container">
      <motion.div
        className="auth-card glass"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h2 className="auth-title">Welcome Back</h2>
        <p className="auth-subtitle">Sign in to your workspace</p>

        <input
          className="auth-input"
          placeholder="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          onKeyDown={onKey}
        />
        <input
          className="auth-input"
          placeholder="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={onKey}
        />

        {status && <div className="auth-status">{status}</div>}

        <button className="auth-button" onClick={submit} disabled={loading}>
          {loading ? "Signing in..." : "Sign In"}
        </button>

        <p className="auth-link" onClick={goForgot}>
          Forgot password?
        </p>

        <p className="auth-footer">
          New here? <span onClick={goSignup}>Create an account</span>
        </p>
      </motion.div>
    </div>
  );
}
