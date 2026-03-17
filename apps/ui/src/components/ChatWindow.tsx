import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { PaperPlaneIcon, HamburgerMenuIcon } from "@radix-ui/react-icons";
import * as Tooltip from "@radix-ui/react-tooltip";
import type { ChatMessageResponse } from "@/api/generated";
import type { ThinkingState } from "@/hooks/useMessageStream";
import { MessageBubble } from "@/components/MessageBubble";
import { ThinkingIndicator } from "@/components/ThinkingIndicator";
import styles from "./ChatWindow.module.css";

interface ChatWindowProps {
  messages: ChatMessageResponse[];
  isSending: boolean;
  thinking: ThinkingState;
  hasActiveSession: boolean;
  sidebarOpen: boolean;
  llmMode: "mock" | "live" | "unknown";
  onSendMessage: (content: string) => void;
  onNewSession: () => void;
  onToggleSidebar: () => void;
}

export function ChatWindow({
  messages,
  isSending,
  thinking,
  hasActiveSession,
  sidebarOpen,
  llmMode,
  onSendMessage,
  onNewSession,
  onToggleSidebar,
}: ChatWindowProps) {
  const [inputValue, setInputValue] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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
    onSendMessage(trimmed);
    setInputValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  }

  if (!hasActiveSession) {
    return (
      <main className={styles.container}>
        {!sidebarOpen && (
          <div className={styles.topBar}>
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
          </div>
        )}
        <div className={styles.emptyState}>
          <div className={styles.emptyLogo}>
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
              <rect width="48" height="48" rx="12" fill="var(--color-accent)" />
              <path d="M14 24h20M24 14v20" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
            </svg>
          </div>
          <h2 className={styles.emptyTitle}>How can I help you today?</h2>
          <p className={styles.emptySubtitle}>Start a conversation about your banking needs</p>
          <button className={styles.startButton} onClick={onNewSession}>
            New conversation
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className={styles.container}>
      {!sidebarOpen && (
        <div className={styles.topBar}>
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
        </div>
      )}

      <div className={styles.messageArea}>
        <div className={styles.messageScroll}>
          {messages.length === 0 && (
            <div className={styles.emptyChat}>
              <p>How can I help you today?</p>
            </div>
          )}
          {messages.map((message) => (
            <MessageBubble key={message.message_id} message={message} />
          ))}
          {isSending && <ThinkingIndicator thinking={thinking} />}
          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className={styles.inputWrapper}>
        <div className={styles.inputContainer}>
          <textarea
            ref={textareaRef}
            className={styles.textarea}
            placeholder="Message Customer Service..."
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
            disabled={isSending || !inputValue.trim()}
            aria-label="Send message"
          >
            <PaperPlaneIcon width={16} height={16} />
          </button>
        </div>
        <p className={styles.disclaimer}>
          {llmMode === "mock" && (
            <span className={styles.mockBadge}>MOCK MODE</span>
          )}
          AI can make mistakes. Verify important banking information.
        </p>
      </div>
    </main>
  );
}
