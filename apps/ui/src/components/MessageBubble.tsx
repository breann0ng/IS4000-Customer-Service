import { PersonIcon } from "@radix-ui/react-icons";
import type { ChatMessageResponse } from "@/api/generated";
import styles from "./MessageBubble.module.css";

interface MessageBubbleProps {
  message: ChatMessageResponse;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`${styles.row} ${isUser ? styles.userRow : styles.assistantRow}`}>
      <div className={styles.avatar}>
        {isUser ? (
          <div className={styles.userAvatar}>
            <PersonIcon width={16} height={16} />
          </div>
        ) : (
          <div className={styles.assistantAvatar}>
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <rect width="20" height="20" rx="4" fill="var(--color-accent)" />
              <path d="M6 10h8M10 6v8" stroke="white" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </div>
        )}
      </div>
      <div className={styles.content}>
        <span className={styles.roleName}>{isUser ? "You" : "Assistant"}</span>
        <div className={styles.text}>{message.content}</div>
      </div>
    </div>
  );
}
