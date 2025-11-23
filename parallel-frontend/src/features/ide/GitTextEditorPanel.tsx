import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  checkGitHubStatus,
  initiateGitHubOAuth,
  listRepositoryFiles,
  getFileContent,
  saveFile,
  commitFile,
  GitHubStatus,
} from "./githubClient";
import "./GitTextEditorPanel.css";

export function GitTextEditorPanel() {
  const [status, setStatus] = useState<GitHubStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [files, setFiles] = useState<Array<{ path: string; type: "file" | "dir" }>>([]);
  const [selectedPath, setSelectedPath] = useState<string>("");
  const [fileContent, setFileContent] = useState<string>("");
  const [isLoadingFile, setIsLoadingFile] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isCommitting, setIsCommitting] = useState(false);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [commitMessage, setCommitMessage] = useState<string>("");

  // Check GitHub connection status on mount
  useEffect(() => {
    loadStatus();
  }, []);

  // Load files when connected
  useEffect(() => {
    if (status?.connected) {
      loadFiles();
    }
  }, [status?.connected]);

  // Load file content when path changes
  useEffect(() => {
    if (selectedPath && status?.connected) {
      loadFileContent(selectedPath);
    }
  }, [selectedPath, status?.connected]);

  const loadStatus = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const githubStatus = await checkGitHubStatus();
      setStatus(githubStatus);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to check GitHub status");
    } finally {
      setIsLoading(false);
    }
  };

  const useMockRepo = () => {
    setStatus({
      connected: true,
      repoName: "mock-repo",
      repoOwner: "demo",
      repoUrl: "https://github.com/demo/mock-repo",
    });
    setFiles([
      { path: "README.md", type: "file" },
      { path: "docs/plan.md", type: "file" },
      { path: "src/app.py", type: "file" },
    ]);
    setSelectedPath("README.md");
    setFileContent("# Mock repo\n\nThis is a mock document. Connect GitHub for real content.");
  };

  const handleConnect = async () => {
    setIsConnecting(true);
    setError(null);
    try {
      const authUrl = await initiateGitHubOAuth();
      if (authUrl) {
        // In real implementation, this would redirect or open OAuth window
        // For now, simulate connection after a delay
        setTimeout(() => {
          loadStatus();
        }, 1500);
      } else {
        setError("Failed to initiate GitHub OAuth");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to connect to GitHub");
    } finally {
      setIsConnecting(false);
    }
  };

  const loadFiles = async () => {
    try {
      const fileList = await listRepositoryFiles();
      setFiles(fileList.files);
      // Auto-select first file if available
      const firstFile = fileList.files.find((f) => f.type === "file");
      if (firstFile) {
        setSelectedPath(firstFile.path);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load files");
    }
  };

  const loadFileContent = async (path: string) => {
    setIsLoadingFile(true);
    try {
      const file = await getFileContent(path);
      setFileContent(file.content);
      setSaveStatus(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load file");
    } finally {
      setIsLoadingFile(false);
    }
  };

  const handleSave = async () => {
    if (!selectedPath || !fileContent.trim()) return;

    setIsSaving(true);
    setSaveStatus(null);
    try {
      const result = await saveFile(selectedPath, fileContent);
      if (result.success) {
        setSaveStatus("File saved successfully");
        setTimeout(() => setSaveStatus(null), 3000);
      } else {
        setError(result.message || "Failed to save file");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save file");
    } finally {
      setIsSaving(false);
    }
  };

  const handleCommit = async () => {
    if (!selectedPath || !fileContent.trim()) return;
    if (!commitMessage.trim()) {
      setError("Please enter a commit message");
      return;
    }

    setIsCommitting(true);
    setError(null);
    try {
      const result = await commitFile(selectedPath, fileContent, commitMessage);
      if (result.success) {
        setSaveStatus(`Committed: ${commitMessage}`);
        setCommitMessage("");
        setTimeout(() => setSaveStatus(null), 5000);
      } else {
        setError(result.message || "Failed to commit");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to commit");
    } finally {
      setIsCommitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="chat-wrapper glass">
        <div className="panel-head">
          <div>
            <p className="eyebrow">IDE</p>
            <h2>Loading...</h2>
          </div>
        </div>
        <div className="git-editor-content">
          <p className="subhead">Checking GitHub connection...</p>
        </div>
      </div>
    );
  }

  if (!status?.connected) {
    return (
      <div className="chat-wrapper glass">
        <div className="panel-head">
          <div>
            <p className="eyebrow">IDE</p>
            <h2>Connect GitHub</h2>
          </div>
        </div>
        <div className="git-editor-content">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="git-connect-state"
          >
            <p className="subhead">
              Connect your GitHub repository to start editing files.
            </p>
            {error && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="git-error"
              >
                {error}
              </motion.div>
            )}
            <div style={{ display: "flex", gap: 12 }}>
              <button
                className="git-connect-btn"
                onClick={handleConnect}
                disabled={isConnecting}
              >
                {isConnecting ? "Connecting..." : "Connect GitHub"}
              </button>
              <button className="git-connect-btn ghost" onClick={useMockRepo}>
                Use mock repo
              </button>
            </div>
          </motion.div>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-wrapper glass">
      <div className="panel-head">
        <div>
          <p className="eyebrow">IDE</p>
          <h2>
            {status.repoOwner}/{status.repoName}
          </h2>
        </div>
      </div>

      <div className="git-editor-content">
        {error && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="git-error"
          >
            {error}
          </motion.div>
        )}

        {saveStatus && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="git-success"
          >
            {saveStatus}
          </motion.div>
        )}

        <div className="git-file-selector">
          <label htmlFor="file-path">File path:</label>
          <div className="git-file-input-group">
            <input
              id="file-path"
              type="text"
              className="git-file-input"
              value={selectedPath}
              onChange={(e) => setSelectedPath(e.target.value)}
              placeholder="e.g., src/main.py"
              list="file-suggestions"
            />
            <datalist id="file-suggestions">
              {files
                .filter((f) => f.type === "file")
                .map((f) => (
                  <option key={f.path} value={f.path} />
                ))}
            </datalist>
            <button
              className="git-load-btn"
              onClick={() => selectedPath && loadFileContent(selectedPath)}
              disabled={!selectedPath || isLoadingFile}
            >
              {isLoadingFile ? "Loading..." : "Load"}
            </button>
          </div>
        </div>

        <div className="git-editor-wrapper">
          {isLoadingFile ? (
            <div className="git-editor-loading">Loading file...</div>
          ) : (
            <textarea
              className="git-editor-textarea"
              value={fileContent}
              onChange={(e) => setFileContent(e.target.value)}
              placeholder="Select a file to edit..."
              spellCheck={false}
            />
          )}
        </div>

        <div className="git-editor-actions">
          <button
            className="git-save-btn"
            onClick={handleSave}
            disabled={!selectedPath || !fileContent.trim() || isSaving}
          >
            {isSaving ? "Saving..." : "Save"}
          </button>
          <div className="git-commit-group">
            <input
              type="text"
              className="git-commit-input"
              value={commitMessage}
              onChange={(e) => setCommitMessage(e.target.value)}
              placeholder="Commit message..."
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleCommit();
                }
              }}
            />
            <button
              className="git-commit-btn"
              onClick={handleCommit}
              disabled={
                !selectedPath ||
                !fileContent.trim() ||
                !commitMessage.trim() ||
                isCommitting
              }
            >
              {isCommitting ? "Committing..." : "Commit"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
