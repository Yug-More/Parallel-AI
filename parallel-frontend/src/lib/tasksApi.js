// Simple API adapter for tasks + team info
const API = import.meta.env.VITE_API_BASE || "http://localhost:8000";

// Always use backend (manager features)
async function j(path, opts = {}) {
  const res = await fetch(`${API}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) throw new Error(await res.text().catch(() => res.statusText));
  return res.status === 204 ? null : res.json();
}

// ---- Team ----
export async function fetchTeam() {
  // Try backend; fall back to mock list
  try {
    // Example backend ideas:
    // - GET /team  -> [{id, name, roles: ['Coordinator'], status:'active'}]
    // - or GET /users
    const data = await j(`/team`);
    return data?.members || [];
  } catch {
    // Mock so UI runs immediately
    return [
      { id: "u1", name: "You", roles: ["Coordinator"], status: "active" },
      { id: "u2", name: "Researcher", roles: ["Analysis"], status: "idle" },
      { id: "u3", name: "Engineer", roles: ["Implementation"], status: "active" },
    ];
  }
}

// ---- Tasks ----
export async function listTasks() {
  try {
    // Example: GET /tasks -> [{id, title, description, assignee_id, status}]
    const data = await j(`/tasks`);
    return data || [];
  } catch {
    return [];
  }
}

export async function createTask({ title, description, assignee_id }) {
  try {
    // Example: POST /tasks
    // body: {title, description, assignee_id}
    return await j(`/tasks`, {
      method: "POST",
      body: JSON.stringify({ title, description, assignee_id }),
    });
  } catch {
    // Fallback: pretend created
    return {
      id: String(Date.now()),
      title,
      description,
      assignee_id,
      status: "new",
      created_at: new Date().toISOString(),
    };
  }
}

export async function updateTaskStatus(taskId, status) {
  try {
    // Example: PATCH /tasks/{id} body:{status}
    return await j(`/tasks/${taskId}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
  } catch {
    return { id: taskId, status };
  }
}

export async function updateUserRole(userId, role) {
  return j(`/users/${userId}/role`, {
    method: "PATCH",
    body: JSON.stringify({ role }),
  });
}

// ---- Notifications (assignee inbox) ----
export async function listMyNotifications(userId) {
  try {
    // Example: GET /users/{id}/notifications
    const data = await j(`/users/${userId}/notifications`);
    return data || [];
  } catch {
    return [];
  }
}

export async function pushTaskNotification({ assignee_id, task }) {
  try {
    // Example: POST /users/{id}/notifications
    await j(`/users/${assignee_id}/notifications`, {
      method: "POST",
      body: JSON.stringify({
        type: "task_assigned",
        task_id: task.id,
        title: task.title,
        message: task.description,
      }),
    });
  } catch {
    // no-op if backend not ready
  }
}
