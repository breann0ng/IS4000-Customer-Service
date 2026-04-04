import { PersonIcon } from "@radix-ui/react-icons";
import type { ChatMessageResponse } from "@/api/generated";
import { StructuredMessage, type MetricItem } from "./StructuredMessage";
import styles from "./MessageBubble.module.css";

interface MessageBubbleProps {
  message: ChatMessageResponse;
  onSuggestionClick?: (suggestion: string) => void;
}

const IMAGE_EXTENSIONS = new Set(["png", "jpg", "jpeg", "gif", "webp"]);

function getFileLabel(fileType: string) {
  if (IMAGE_EXTENSIONS.has(fileType)) return "IMG";
  if (fileType === "pdf") return "PDF";
  if (fileType === "docx") return "DOC";
  if (fileType === "xlsx" || fileType === "xls") return "XLS";
  return "FILE";
}

export function MessageBubble({ message, onSuggestionClick }: MessageBubbleProps) {
  const isUser = message.role === "user";

  // Safely extract metadata from the flexible metadata object
  const metadata = message.metadata as any;
  const metrics = metadata?.metrics as MetricItem[] | undefined;
  const suggestions = metadata?.suggestions as string[] | undefined;

  // Check if the user message has an attached file
  const ctx = isUser ? (message.context as any) : null;
  const attachedFile = ctx?.attached_file as string | undefined;
  const fileType = ctx?.file_type as string | undefined;
  const imageBase64 = ctx?.image_base64 as string | undefined;
  const isImage = fileType ? IMAGE_EXTENSIONS.has(fileType) : false;

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
        {attachedFile && (
          <div className={styles.attachmentBlock}>
            {isImage && imageBase64 ? (
              <div className={styles.imagePreview}>
                <img
                  src={`data:image/${fileType === "jpg" ? "jpeg" : fileType};base64,${imageBase64}`}
                  alt={attachedFile}
                  className={styles.previewImg}
                />
                <span className={styles.imageFileName}>{attachedFile}</span>
              </div>
            ) : (
              <div className={styles.fileCard}>
                <span className={styles.fileLabel}>{getFileLabel(fileType ?? "")}</span>
                <span className={styles.fileName}>{attachedFile}</span>
              </div>
            )}
          </div>
        )}
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
