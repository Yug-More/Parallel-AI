import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Collaborator, ChatMessage, sendChatMessage } from "./api";
import { CollaboratorList } from "./CollaboratorList";
import styles from "./ide.module.css";

interface ChatPanelProps {
  collaborators: Collaborator[];
}

export function ChatPanel({ collaborators }: ChatPanelProps) {
  const [activeCollaboratorId, setActiveCollaboratorId] = useState<string | null>(
    collaborators[0]?.id || null
  );
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const activeCollaborator = collaborators.find((c) => c.id === activeCollaboratorId);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !activeCollaboratorId || isSending) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      sender: "You",
      senderId: "user",
      text: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsSending(true);

    try {
      const response = await sendChatMessage(activeCollaboratorId, input);
      setMessages((prev) => [...prev, response]);
    } catch (error) {
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        sender: activeCollaborator?.name || "Agent",
        senderId: activeCollaboratorId,
        text: `Error: ${error instanceof Error ? error.message : "Failed to send message"}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className={styles.chatPanel}>
      <div className={styles.chatHeader}>
        <div className={styles.chatTitle}>AI Collaborators</div>
        <CollaboratorList
          collaborators={collaborators}
          activeId={activeCollaboratorId}
          onSelect={setActiveCollaboratorId}
        />
      </div>

      <div className={styles.messagesContainer}>
        <AnimatePresence>
          {messages.length === 0 ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className={styles.message}
              style={{
                alignSelf: "center",
                color: "var(--text-secondary)",
                fontStyle: "italic",
                textAlign: "center",
              }}
            >
              Start a conversation with {activeCollaborator?.name || "an agent"}...
            </motion.div>
          ) : (
            messages.map((message) => (
              <motion.div
                key={message.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
                className={`${styles.message} ${
                  message.senderId === "user" ? styles.messageUser : styles.messageAgent
                }`}
              >
                {message.senderId !== "user" && (
                  <div className={styles.messageSender}>{message.sender}</div>
                )}
                {message.text}
              </motion.div>
            ))
          )}
        </AnimatePresence>
        <div ref={messagesEndRef} />
      </div>

      <div className={styles.chatInputContainer}>
        <form className={styles.chatInputForm} onSubmit={handleSend}>
          <textarea
            className={styles.chatInput}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={`Message ${activeCollaborator?.name || "agent"}...`}
            rows={2}
            disabled={isSending}
          />
          <button
            type="submit"
            className={styles.chatSendBtn}
            disabled={!input.trim() || isSending}
          >
            {isSending ? "..." : "Send"}
          </button>
        </form>
      </div>
    </div>
  );
}

