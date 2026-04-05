import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import {
  PaperPlaneIcon,
  HamburgerMenuIcon,
  BarChartIcon,
  CardStackIcon,
  QuestionMarkCircledIcon,
  ExitIcon,
  UploadIcon,
  Cross2Icon,
} from "@radix-ui/react-icons";
import * as Tooltip from "@radix-ui/react-tooltip";
import type { ChatMessageResponse, UserProfile } from "@/api/generated";
import type { ThinkingState } from "@/hooks/useMessageStream";
import type { FileAttachment } from "@/hooks/useFileUpload";
import { MessageBubble } from "@/components/MessageBubble";
import { ThinkingIndicator } from "@/components/ThinkingIndicator";
import styles from "./ChatWindow.module.css";

interface ChatWindowProps {
  messages: ChatMessageResponse[];
  isSending: boolean;
  thinking: ThinkingState;
  sidebarOpen: boolean;
  user: UserProfile;
  attachment: FileAttachment | null;
  onLogout: () => void;
  onSendMessage: (content: string, fileData?: { fileContext?: string; fileName?: string; imageBase64?: string | null; fileType?: string }) => void;
  onToggleSidebar: () => void;
  onFileSelect: (file: File) => void;
  onClearAttachment: () => void;
}

const ACCEPTED_FILE_TYPES = ".pdf,.docx,.xlsx,.xls,.png,.jpg,.jpeg,.gif,.webp";

function getFileIcon(fileType: string) {
  if (["png", "jpg", "jpeg", "gif", "webp"].includes(fileType)) return "IMG";
  if (fileType === "pdf") return "PDF";
  if (fileType === "docx") return "DOC";
  if (["xlsx", "xls"].includes(fileType)) return "XLS";
  return "FILE";
}

export function ChatWindow({
  messages,
  isSending,
  thinking,
  sidebarOpen,
  user,
  attachment,
  onLogout,
  onSendMessage,
  onToggleSidebar,
  onFileSelect,
  onClearAttachment,
}: ChatWindowProps) {
  const [inputValue, setInputValue] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [inputValue]);

  function handleSend() {
    const trimmed = inputValue.trim();
    if (!trimmed || isSending) return;
    if (attachment && attachment.isUploading) return;

    if (attachment && !attachment.error) {
      onSendMessage(trimmed, {
        fileContext: attachment.extractedText || undefined,
        fileName: attachment.filename,
        imageBase64: attachment.imageBase64,
        fileType: attachment.fileType,
      });
      onClearAttachment();
    } else {
      onSendMessage(trimmed);
    }
    setInputValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }

  function handlePromptClick(text: string) {
    if (isSending) return;
    onSendMessage(text);
  }

  function handleFileButtonClick() {
    fileInputRef.current?.click();
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) {
      onFileSelect(file);
    }
    // Reset so the same file can be re-selected
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <main className={styles.container}>
      <div className={styles.topBar}>
        <div className={styles.topBarLeft}>
          {!sidebarOpen && (
            <Tooltip.Provider delayDuration={300}>
              <Tooltip.Root>
                <Tooltip.Trigger asChild>
                  <button className={styles.menuButton} onClick={onToggleSidebar} aria-label="Open sidebar">
                    <HamburgerMenuIcon width={18} height={18} />
                  </button>
                </Tooltip.Trigger>
                <Tooltip.Content className={styles.tooltip} side="bottom" sideOffset={4}>
                  Open sidebar
                </Tooltip.Content>
              </Tooltip.Root>
            </Tooltip.Provider>
          )}
          <span className={styles.topBarTitle}><strong style={{color: "var(--color-accent)", fontWeight: "bold"}}>Red.</strong> Your UBS AI Assistant</span>
        </div>
        <div className={styles.topBarRight}>
          <div className={styles.userRow}>
            <div className={styles.avatar}>
              {user.display_name.charAt(0).toUpperCase()}
            </div>
            <Tooltip.Provider delayDuration={300}>
              <Tooltip.Root>
                <Tooltip.Trigger asChild>
                  <button className={styles.iconButton} onClick={onLogout} aria-label="Sign out">
                    <ExitIcon width={15} height={15} />
                  </button>
                </Tooltip.Trigger>
                <Tooltip.Content className={styles.tooltip} side="right" sideOffset={8}>
                  Sign out
                </Tooltip.Content>
              </Tooltip.Root>
            </Tooltip.Provider>
          </div>
        </div>
      </div>

      {messages.length === 0 ? (
        <div className={styles.emptyState}>
          <div className={styles.greetingHeader}>
            <h2 className={styles.emptyTitle}>Hello, {user.display_name.split(" ")[0]}</h2>
            <h2 className={styles.emptyTitleSecondary}>How can I help you?</h2>
            <p className={styles.emptySubtitle}>Your AI assistant for personalised insights and answers on your UBS account, instantly.</p>
          </div>
          
          <div className={styles.suggestedPromptsHeader}>Suggested prompts</div>
          <div className={styles.suggestedPrompts}>
            <button className={styles.promptCard} onClick={() => handlePromptClick("Summarize my recent portfolio performance")}>
              <p>Summarize my recent portfolio performance</p>
              <div className={styles.promptIcon}><BarChartIcon width={16} height={16} style={{color: "var(--color-accent)"}}/></div>
            </button>
            <button className={styles.promptCard} onClick={() => handlePromptClick("Can you replace my damaged credit card?")}>
              <p>Can you replace my damaged credit card?</p>
              <div className={styles.promptIcon}><CardStackIcon width={16} height={16} style={{color: "var(--color-accent)"}}/></div>
            </button>
            <button className={styles.promptCard} onClick={() => handlePromptClick("Explain the fees on my last statement")}>
              <p>Explain the fees on my last statement</p>
              <div className={styles.promptIcon}><QuestionMarkCircledIcon width={16} height={16} style={{color: "var(--color-accent)"}}/></div>
            </button>
          </div>
        </div>
      ) : (
        <div className={styles.messageArea}>
          <div className={styles.messageScroll}>
          {messages.map((message) => (
            <MessageBubble 
              key={message.message_id} 
              message={message} 
              onSuggestionClick={onSendMessage}
            />
          ))}
          {isSending && <ThinkingIndicator thinking={thinking} />}
          <div ref={messagesEndRef} />
          </div>
        </div>
      )}

      <div className={styles.inputWrapper}>
        {attachment && (
          <div className={styles.attachmentPreview}>
            <div className={styles.attachmentChip}>
              <span className={styles.attachmentIcon}>{getFileIcon(attachment.fileType)}</span>
              <span className={styles.attachmentName}>{attachment.filename}</span>
              {attachment.isUploading && <span className={styles.attachmentStatus}>Parsing...</span>}
              {attachment.error && <span className={styles.attachmentError}>{attachment.error}</span>}
              <button
                className={styles.attachmentRemove}
                onClick={onClearAttachment}
                aria-label="Remove attachment"
              >
                <Cross2Icon width={12} height={12} />
              </button>
            </div>
          </div>
        )}
        <div className={styles.inputContainer}>
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_FILE_TYPES}
            onChange={handleFileChange}
            className={styles.hiddenFileInput}
            aria-label="Upload file"
          />
          <Tooltip.Provider delayDuration={300}>
            <Tooltip.Root>
              <Tooltip.Trigger asChild>
                <button
                  className={styles.attachButton}
                  onClick={handleFileButtonClick}
                  disabled={isSending || !!attachment}
                  aria-label="Attach file"
                >
                  <UploadIcon width={16} height={16} />
                </button>
              </Tooltip.Trigger>
              <Tooltip.Content className={styles.tooltip} side="top" sideOffset={4}>
                Attach a file (PDF, DOCX, Excel, Image)
              </Tooltip.Content>
            </Tooltip.Root>
          </Tooltip.Provider>
          <textarea
            ref={textareaRef}
            className={styles.textarea}
            placeholder="Talk with Red"
            value={inputValue}
            onChange={(event) => setInputValue(event.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isSending}
            rows={1}
            autoFocus
          />
          <button
            className={styles.sendButton}
            onClick={handleSend}
            disabled={isSending || !inputValue.trim() || (!!attachment && attachment.isUploading)}
            aria-label="Send message"
          >
            <PaperPlaneIcon width={16} height={16} />
          </button>
        </div>
        <p className={styles.disclaimer}>
          UBS and external data are strictly forbidden. Red uses AI. Check for mistakes. You remain responsible for your initiated prompts and shared content.
        </p>
      </div>
    </main>
  );
}
