// GitHub API client with graceful mocks
// Replace these with real FastAPI endpoints when backend is ready

const apiBase = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export interface GitHubStatus {
  connected: boolean;
  repoName?: string;
  repoOwner?: string;
  repoUrl?: string;
}

export interface GitHubFile {
  path: string;
  content: string;
  sha?: string;
}

export interface GitHubFileList {
  files: Array<{ path: string; type: "file" | "dir" }>;
}

// Mock state - in real implementation, this would come from backend
let mockConnected = false;
let mockRepoName = "";
let mockRepoOwner = "";
let mockFiles: Array<{ path: string; type: "file" | "dir" }> = [];
let mockFileContent: Record<string, string> = {};

/**
 * Check if GitHub is connected for the current user/project
 */
export async function checkGitHubStatus(): Promise<GitHubStatus> {
  try {
    const response = await fetch(`${apiBase}/api/github/status`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    });

    if (response.ok) {
      const data = await response.json();
      return {
        connected: data.connected || false,
        repoName: data.repo_name,
        repoOwner: data.repo_owner,
        repoUrl: data.repo_url,
      };
    }
  } catch (error) {
    console.warn("GitHub status endpoint not available, using mock:", error);
  }

  // Graceful mock fallback
  return {
    connected: mockConnected,
    repoName: mockRepoName || undefined,
    repoOwner: mockRepoOwner || undefined,
    repoUrl: mockRepoName
      ? `https://github.com/${mockRepoOwner}/${mockRepoName}`
      : undefined,
  };
}

/**
 * Initiate GitHub OAuth flow
 * Returns the OAuth URL to redirect to, or null if error
 */
export async function initiateGitHubOAuth(): Promise<string | null> {
  try {
    // Real implementation would call: GET /api/github/oauth/authorize
    const response = await fetch(`${apiBase}/api/github/oauth/authorize`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    });

    if (response.ok) {
      const data = await response.json();
      return data.auth_url || null;
    }
  } catch (error) {
    console.warn("GitHub OAuth endpoint not available, using mock:", error);
  }

  // Graceful mock: simulate OAuth success after a delay
  setTimeout(() => {
    mockConnected = true;
    mockRepoName = "parallel-ai";
    mockRepoOwner = "demo-user";
    mockFiles = [
      { path: "README.md", type: "file" },
      { path: "src", type: "dir" },
      { path: "src/main.py", type: "file" },
      { path: "package.json", type: "file" },
    ];
  }, 1000);

  // Return a mock URL that would trigger the OAuth flow
  // In real implementation, this would redirect the browser
  return `${apiBase}/api/github/oauth/authorize`;
}

/**
 * List files in the connected repository
 */
export async function listRepositoryFiles(
  path: string = ""
): Promise<GitHubFileList> {
  try {
    const response = await fetch(
      `${apiBase}/api/github/repo/files?path=${encodeURIComponent(path)}`,
      {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      }
    );

    if (response.ok) {
      const data = await response.json();
      return { files: data.files || [] };
    }
  } catch (error) {
    console.warn("List files endpoint not available, using mock:", error);
  }

  // Graceful mock fallback
  if (path === "") {
    return { files: mockFiles };
  }
  // Filter by path prefix for mock
  return {
    files: mockFiles.filter((f) => f.path.startsWith(path)),
  };
}

/**
 * Get file content from repository
 */
export async function getFileContent(path: string): Promise<GitHubFile> {
  try {
    const response = await fetch(
      `${apiBase}/api/github/repo/file?path=${encodeURIComponent(path)}`,
      {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      }
    );

    if (response.ok) {
      const data = await response.json();
      return {
        path: data.path,
        content: data.content || "",
        sha: data.sha,
      };
    }
  } catch (error) {
    console.warn("Get file endpoint not available, using mock:", error);
  }

  // Graceful mock fallback
  if (mockFileContent[path]) {
    return {
      path,
      content: mockFileContent[path],
    };
  }

  // Default mock content
  const defaultContent = `# ${path}\n\nThis is a mock file. Connect to GitHub to see real content.`;
  mockFileContent[path] = defaultContent;
  return {
    path,
    content: defaultContent,
  };
}

/**
 * Save file content (without committing)
 */
export async function saveFile(
  path: string,
  content: string
): Promise<{ success: boolean; message?: string }> {
  try {
    // Real implementation would call: PUT /api/github/repo/file
    const response = await fetch(`${apiBase}/api/github/repo/file`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, content }),
    });

    if (response.ok) {
      const data = await response.json();
      return { success: true, message: data.message };
    } else {
      const error = await response.json().catch(() => ({}));
      return {
        success: false,
        message: error.detail || "Failed to save file",
      };
    }
  } catch (error) {
    console.warn("Save file endpoint not available, using mock:", error);
  }

  // Graceful mock fallback
  mockFileContent[path] = content;
  return { success: true, message: "File saved (mock)" };
}

/**
 * Commit and push changes to repository
 */
export async function commitFile(
  path: string,
  content: string,
  message: string
): Promise<{ success: boolean; message?: string; commitSha?: string }> {
  try {
    // Real implementation would call: POST /api/github/repo/commit
    const response = await fetch(`${apiBase}/api/github/repo/commit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, content, message }),
    });

    if (response.ok) {
      const data = await response.json();
      return {
        success: true,
        message: data.message,
        commitSha: data.commit_sha,
      };
    } else {
      const error = await response.json().catch(() => ({}));
      return {
        success: false,
        message: error.detail || "Failed to commit",
      };
    }
  } catch (error) {
    console.warn("Commit endpoint not available, using mock:", error);
  }

  // Graceful mock fallback
  mockFileContent[path] = content;
  return {
    success: true,
    message: "Changes committed (mock)",
    commitSha: "mock-commit-sha",
  };
}
