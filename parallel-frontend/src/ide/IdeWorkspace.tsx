import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  EditorCell as CellType,
  Collaborator,
  getCollaborators,
  addCell,
} from "./api";
import { EditorCell as EditorCellComponent } from "./EditorCell";
import { ChatPanel } from "./ChatPanel";
import styles from "./ide.module.css";

export function IdeWorkspace() {
  const [cells, setCells] = useState<CellType[]>([]);
  const [collaborators, setCollaborators] = useState<Collaborator[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Load initial data
    const loadData = async () => {
      try {
        const [collabs, initialCell] = await Promise.all([
          getCollaborators(),
          addCell("code"),
        ]);
        setCollaborators(collabs);
        setCells([initialCell]);
      } catch (error) {
        console.error("Failed to load initial data:", error);
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, []);

  const handleCellUpdate = (id: string, content: string) => {
    setCells((prev) =>
      prev.map((cell) => (cell.id === id ? { ...cell, content } : cell))
    );
  };

  const handleCellOutputUpdate = (id: string, output: string) => {
    setCells((prev) =>
      prev.map((cell) => (cell.id === id ? { ...cell, output } : cell))
    );
  };

  const handleCellDelete = (id: string) => {
    setCells((prev) => prev.filter((cell) => cell.id !== id));
  };

  const handleAddCell = async (type: "code" | "markdown") => {
    try {
      const newCell = await addCell(type);
      setCells((prev) => [...prev, newCell]);
    } catch (error) {
      console.error("Failed to add cell:", error);
    }
  };

  if (isLoading) {
    return (
      <div className={styles.ideWorkspace}>
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            style={{ color: "var(--text-secondary)" }}
          >
            Loading IDE...
          </motion.div>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.ideWorkspace}>
      {/* Left: Editor Section */}
      <div className={styles.editorSection}>
        <div className={styles.editorHeader}>
          <h2 className={styles.editorTitle}>Notebook</h2>
          <div className={styles.editorActions}>
            <button
              className={styles.btn}
              onClick={() => handleAddCell("markdown")}
            >
              + Markdown
            </button>
            <button
              className={`${styles.btn} ${styles.btnPrimary}`}
              onClick={() => handleAddCell("code")}
            >
              + Code Cell
            </button>
          </div>
        </div>

        <div className={styles.cellsContainer}>
          <AnimatePresence mode="popLayout">
            {cells.map((cell) => (
              <EditorCellComponent
                key={cell.id}
                cell={cell}
                onUpdate={handleCellUpdate}
                onDelete={handleCellDelete}
                onOutputUpdate={handleCellOutputUpdate}
              />
            ))}
          </AnimatePresence>
          {cells.length === 0 && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              style={{
                textAlign: "center",
                color: "var(--text-secondary)",
                padding: "40px",
                fontStyle: "italic",
              }}
            >
              No cells yet. Add a code or markdown cell to get started.
            </motion.div>
          )}
        </div>
      </div>

      {/* Right: Chat Section */}
      <div className={styles.chatSection}>
        <ChatPanel collaborators={collaborators} />
      </div>
    </div>
  );
}

