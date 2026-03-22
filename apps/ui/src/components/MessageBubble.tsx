import { PersonIcon } from "@radix-ui/react-icons";
import type { ChatMessageResponse } from "@/api/generated";
import { StructuredMessage, type MetricItem } from "./StructuredMessage";
import styles from "./MessageBubble.module.css";

interface MessageBubbleProps {
  message: ChatMessageResponse;
  onSuggestionClick?: (suggestion: string) => void;
}

export function MessageBubble({ message, onSuggestionClick }: MessageBubbleProps) {
  const isUser = message.role === "user";

  // Safely extract metadata from the flexible metadata object
  const metadata = message.metadata as any;
  const metrics = metadata?.metrics as MetricItem[] | undefined;
  const suggestions = metadata?.suggestions as string[] | undefined;

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
        <div className={styles.text}>
          {isUser ? (
            message.content
          ) : (
            <StructuredMessage
              content={message.content}
              metrics={metrics}
              suggestions={suggestions}
              onSuggestionClick={onSuggestionClick || (() => {})}
            />
          )}
        </div>
      </div>
    </div>
  );
}
