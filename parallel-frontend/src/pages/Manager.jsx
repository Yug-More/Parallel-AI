import { useEffect, useState, useMemo } from "react";
import { motion } from "framer-motion";
import "./Manager.css";

import {
  fetchTeam,
  listTasks,            // keeps "All Tasks" view
  createTask,
  updateTaskStatus,
  pushTaskNotification, // best-effort notify
  updateUserRole,
} from "../lib/tasksApi";

import { useTasks } from "../context/TaskContext";

export default function Manager({
  currentUser = { id: "demo-user", name: "You" },
}) {
  const [team, setTeam] = useState([]);
  const { tasks, setTasks } = useTasks();
  const [loading, setLoading] = useState(true);

  // UI-only placeholder permissions (not persisted)
  // shape: { [userId]: { frontend: boolean, backend: boolean } }
  const [permissions, setPermissions] = useState({});

  // create-task form
  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");
  const [assignee, setAssignee] = useState("");
  const roleOptions =
    (import.meta.env.VITE_ROLE_OPTIONS || "Product,Engineering,Design,Data,Ops,Other")
      .split(",")
      .map((r) => r.trim())
      .filter(Boolean);

  // Hide completed tasks immediately after marking complete
  const visibleTasks = useMemo(
    () => tasks.filter((t) => t.status !== "complete"),
    [tasks]
  );

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const [membersRes, tasksRes] = await Promise.all([
          fetchTeam(),
          listTasks(),
        ]);
        const members = membersRes || [];
        setTeam(members);
        setTasks(tasksRes || []);
        setAssignee(members[0]?.id || "");

        // seed default permissions per member (both checked)
        setPermissions((prev) => {
          const next = { ...prev };
          for (const m of members) {
            if (!next[m.id]) next[m.id] = { frontend: true, backend: true };
          }
          return next;
        });
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [setTasks]);

  const togglePerm = (userId, key) => {
    setPermissions((prev) => ({
      ...prev,
      [userId]: { ...prev[userId], [key]: !prev[userId]?.[key] },
    }));
  };

  const changeRole = async (userId, role) => {
    try {
      const updated = await updateUserRole(userId, role);
      setTeam((prev) => prev.map((m) => (m.id === userId ? { ...m, roles: [updated.role] } : m)));
    } catch (err) {
      console.error("Failed to update role", err);
    }
  };

  const create = async () => {
    if (!title.trim() || !assignee) return;
    const task = await createTask({
      title,
      description: desc,
      assignee_id: assignee,
    });
    setTasks((prev) => [task, ...prev]);
    setTitle("");
    setDesc("");
    try {
      await pushTaskNotification({ assignee_id: assignee, task });
    } catch {
      /* best-effort */
    }
  };

  const setStatus = async (taskId, status) => {
    const updated = await updateTaskStatus(taskId, status);
    setTasks((prev) =>
      status === "complete"
        ? prev.filter((t) => t.id !== taskId) // hide immediately
        : prev.map((t) =>
            t.id === taskId ? { ...t, status: updated.status } : t
          )
    );
  };

  if (loading) {
    return (
      <div className="manager-wrap">
        <div className="manager-card">
          <div className="manager-heading">
            <div className="manager-title">Project Manager</div>
          </div>
          <div className="manager-list">Loading…</div>
        </div>
        <div className="manager-pane" />
      </div>
    );
  }

  return (
    <div className="manager-wrap">
      {/* Left: Team + Roles + Permissions (placeholder UI) */}
      <div className="manager-card">
        <div className="manager-heading">
            <div className="manager-title">Team</div>
          </div>

          <div className="manager-list">
            {team.length === 0 && <div>No teammates yet.</div>}
            {team.map((m) => (
              <div key={m.id} className="member">
                <div style={{ width: "100%" }}>
                  <div style={{ fontWeight: 700 }}>{m.name}</div>
                  <div className="roles">
                    {(m.roles || ["—"]).join(", ")}
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <select
                      value={m.roles?.[0] || ""}
                      onChange={(e) => changeRole(m.id, e.target.value)}
                    >
                      <option value="">Select role</option>
                      {roleOptions.map((opt) => (
                        <option key={opt} value={opt}>
                          {opt}
                        </option>
                      ))}
                    </select>
                  </div>

                {/* Permissions placeholder (not persisted) */}
                <div
                  className="perm-row"
                  style={{
                    display: "flex",
                    gap: 12,
                    marginTop: 8,
                    fontSize: 13,
                  }}
                >
                  <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    <input
                      type="checkbox"
                      checked={permissions[m.id]?.frontend ?? true}
                      onChange={() => togglePerm(m.id, "frontend")}
                    />
                    Frontend
                  </label>
                  <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    <input
                      type="checkbox"
                      checked={permissions[m.id]?.backend ?? true}
                      onChange={() => togglePerm(m.id, "backend")}
                    />
                    Backend
                  </label>
                </div>
              </div>

              <div className="roles">{m.status || "active"}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Right: Create Task + All Tasks */}
      <div
        className="manager-pane"
        style={{ display: "grid", gridTemplateRows: "auto 1fr" }}
      >
        <div className="manager-heading">
          <div className="manager-title">Tasks</div>
          <div style={{ opacity: 0.7 }}>Assign work to teammates</div>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "360px 1fr",
            gap: 16,
            padding: 16,
          }}
        >
          {/* Create Task */}
          <div className="manager-card" style={{ padding: 0 }}>
            <div className="manager-heading">
              <div className="manager-title">Create Task</div>
            </div>
            <div className="task-form">
              <input
                placeholder="Title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
              <textarea
                placeholder="Description / details"
                value={desc}
                onChange={(e) => setDesc(e.target.value)}
              />
              <select
                value={assignee}
                onChange={(e) => setAssignee(e.target.value)}
              >
                {team.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>
              <button className="btn primary" onClick={create}>
                Create & Notify
              </button>
            </div>
          </div>

          {/* All Tasks */}
          <div
            className="manager-card"
            style={{ padding: 0, display: "grid", gridTemplateRows: "auto 1fr" }}
          >
            <div className="manager-heading">
              <div className="manager-title">All Tasks</div>
              <div className="roles">Newest first</div>
            </div>

            <div className="manager-list" style={{ overflowY: "auto" }}>
              {visibleTasks.length === 0 && <div>No tasks yet.</div>}

              {visibleTasks.map((t) => (
                <motion.div
                  key={t.id}
                  className="task-row"
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                >
                  <div>
                    <div className="task-col-title">{t.title}</div>
                    <div className="roles">{t.description}</div>
                  </div>

                  <div className="task-col-status">
                    {team.find((m) => m.id === t.assignee_id)?.name || "—"}
                  </div>

                  <div className="task-actions">
                    <span className="roles" style={{ alignSelf: "center" }}>
                      {t.status || "new"}
                    </span>
                    <button
                      className="btn"
                      onClick={() => setStatus(t.id, "in_progress")}
                    >
                      In Progress
                    </button>
                    <button
                      className="btn"
                      onClick={() => setStatus(t.id, "complete")}
                    >
                      Complete
                    </button>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
