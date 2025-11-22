// src/App.jsx
import { useState } from "react";
import "./App.css";

import Landing from "./components/Landing";
import Dashboard from "./components/Dashboard";
import ThemeToggle from "./components/ThemeToggle";

export default function App() {
  const [entered, setEntered] = useState(false);

  return (
    <div className="app-container">
      {!entered ? (
        <Landing onEnter={() => setEntered(true)} />
      ) : (
        <>
          <ThemeToggle />
          <Dashboard />
        </>
      )}
    </div>
  );
}
