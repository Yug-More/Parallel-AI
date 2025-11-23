import { motion } from "framer-motion";
import { Collaborator } from "./api";
import styles from "./ide.module.css";

interface CollaboratorListProps {
  collaborators: Collaborator[];
  activeId: string | null;
  onSelect: (id: string) => void;
}

export function CollaboratorList({
  collaborators,
  activeId,
  onSelect,
}: CollaboratorListProps) {
  const getStatusDotClass = (status: Collaborator["status"]) => {
    switch (status) {
      case "active":
        return styles.statusDotActive;
      case "idle":
        return styles.statusDotIdle;
      default:
        return styles.statusDotOffline;
    }
  };

  return (
    <div className={styles.collaboratorSelector}>
      {collaborators.map((collaborator) => (
        <motion.div
          key={collaborator.id}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.2 }}
          className={`${styles.collaboratorItem} ${
            activeId === collaborator.id ? styles.collaboratorItemActive : ""
          }`}
          onClick={() => onSelect(collaborator.id)}
        >
          <div className={`${styles.statusDot} ${getStatusDotClass(collaborator.status)}`} />
          <div className={styles.collaboratorInfo}>
            <div className={styles.collaboratorName}>{collaborator.name}</div>
            <div className={styles.collaboratorRole}>{collaborator.role}</div>
          </div>
        </motion.div>
      ))}
    </div>
  );
}

