import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { executeCell, saveCell, deleteCell, EditorCell as CellType } from "./api";
import styles from "./ide.module.css";

interface EditorCellProps {
  cell: CellType;
  onUpdate: (id: string, content: string) => void;
  onDelete: (id: string) => void;
  onOutputUpdate: (id: string, output: string) => void;
}

export function EditorCell({ cell, onUpdate, onDelete, onOutputUpdate }: EditorCellProps) {
  const [content, setContent] = useState(cell.content);
  const [isRunning, setIsRunning] = useState(false);
  const [output, setOutput] = useState(cell.output || "");

  useEffect(() => {
    // Auto-save after content changes
    const timeoutId = setTimeout(() => {
      saveCell(cell.id, content);
    }, 500);
    return () => clearTimeout(timeoutId);
  }, [content, cell.id]);

  const handleContentChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newContent = e.target.value;
    setContent(newContent);
    onUpdate(cell.id, newContent);
  };

  const handleRun = async () => {
    if (cell.type !== "code" || isRunning) return;
    
    setIsRunning(true);
    try {
      const result = await executeCell(cell.id, content);
      setOutput(result);
      onOutputUpdate(cell.id, result);
    } catch (error) {
      setOutput(`Error: ${error instanceof Error ? error.message : "Execution failed"}`);
    } finally {
      setIsRunning(false);
    }
  };

  const handleDelete = () => {
    deleteCell(cell.id);
    onDelete(cell.id);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
      className={styles.cell}
    >
      <div className={styles.cellHeader}>
        <span className={styles.cellType}>
          {cell.type === "code" ? "Code" : "Markdown"}
        </span>
        <div className={styles.cellActions}>
          {cell.type === "code" && (
            <button
              className={`${styles.cellBtn} ${isRunning ? styles.cellBtnRunning : ""}`}
              onClick={handleRun}
              disabled={isRunning}
            >
              {isRunning ? "Running..." : "Run"}
            </button>
          )}
          <button className={styles.cellBtn} onClick={handleDelete}>
            Delete
          </button>
        </div>
      </div>
      <div className={styles.cellContent}>
        <textarea
          className={styles.cellTextarea}
          value={content}
          onChange={handleContentChange}
          placeholder={
            cell.type === "code"
              ? `# Your ${cell.language || "code"} here`
              : "# Markdown content"
          }
          spellCheck={cell.type === "markdown"}
        />
        {cell.type === "code" && (
          <div className={`${styles.cellOutput} ${!output ? styles.cellOutputEmpty : ""}`}>
            {output || "Output will appear here..."}
          </div>
        )}
      </div>
    </motion.div>
  );
}

