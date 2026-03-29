import { useState } from "react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import * as Tooltip from "@radix-ui/react-tooltip";
import {
  PlusIcon,
  DotsHorizontalIcon,
  Pencil1Icon,
  ArchiveIcon,
  ResetIcon,
  TrashIcon,
  ChatBubbleIcon,
  HamburgerMenuIcon,
  StarIcon,
  MoonIcon,
  SunIcon,
} from "@radix-ui/react-icons";
import type { ChatSessionSummary } from "@/api/generated";
import styles from "./Sidebar.module.css";

interface SidebarProps {
  sessions: ChatSessionSummary[];
  activeSessionId: string | null;
  isLoading: boolean;
  isOpen: boolean;
  showArchived: boolean;
  theme: { theme: "light" | "dark"; toggleTheme: () => void };
  currentView: "chat" | "performance";
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
  onDeleteSession: (sessionId: string) => void;
  onRenameSession: (sessionId: string, title: string) => void;
  onArchiveSession: (sessionId: string) => void;
  onUnarchiveSession: (sessionId: string) => void;
  onToggleArchived: () => void;
  onToggle: () => void;
  onNavigatePerformance: () => void;
  onNavigateChat: () => void;
  width: number;
  onWidthChange: (width: number) => void;
}

export function Sidebar({
  sessions,
  activeSessionId,
  isLoading,
  isOpen,
  showArchived,
  theme,
  currentView,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  onRenameSession,
  onArchiveSession,
  onUnarchiveSession,
  onToggleArchived,
  onToggle,
  onNavigatePerformance,
  onNavigateChat,
  width,
  onWidthChange,
}: SidebarProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [isResizing, setIsResizing] = useState(false);

  function handleStartRename(sessionId: string, currentTitle: string) {
    setEditingId(sessionId);
    setEditTitle(currentTitle);
  }

  function handleFinishRename(sessionId: string) {
    if (editTitle.trim()) {
      onRenameSession(sessionId, editTitle.trim());
    }
    setEditingId(null);
  }

  function handleMouseDown(e: React.MouseEvent) {
    e.preventDefault();
    setIsResizing(true);
    const startX = e.clientX;
    const startWidth = width;

    function handleMouseMove(e: MouseEvent) {
      const newWidth = Math.min(Math.max(startWidth + (e.clientX - startX), 200), 600);
      onWidthChange(newWidth);
    }

    function handleMouseUp() {
      setIsResizing(false);
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "default";
    }

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    document.body.style.cursor = "ew-resize";
  }

  return (
    <Tooltip.Provider delayDuration={300}>
      <aside 
        className={`${styles.sidebar} ${isOpen ? styles.open : styles.closed}`}
        style={{ 
          width: isOpen ? `${width}px` : undefined, 
          minWidth: isOpen ? `${width}px` : undefined,
          transition: isResizing ? "none" : undefined,
          overflow: isOpen ? "visible" : "hidden"
        }}
      >
        <div className={styles.resizeHandle} onMouseDown={handleMouseDown} />
        <div className={styles.header}>
          <Tooltip.Root>
            <Tooltip.Trigger asChild>
              <button className={styles.iconButton} onClick={onToggle} aria-label="Toggle sidebar">
                <HamburgerMenuIcon width={18} height={18} />
              </button>
            </Tooltip.Trigger>
            <Tooltip.Content className={styles.tooltip} side="right" sideOffset={8}>
              Toggle sidebar
            </Tooltip.Content>
          </Tooltip.Root>

          <Tooltip.Root>
            <Tooltip.Trigger asChild>
              <button className={styles.iconButton} onClick={onNewSession} aria-label="New chat">
                <PlusIcon width={18} height={18} />
              </button>
            </Tooltip.Trigger>
            <Tooltip.Content className={styles.tooltip} side="right" sideOffset={8}>
              New chat
            </Tooltip.Content>
          </Tooltip.Root>
        </div>

        <nav className={styles.sessionList}>
          {isLoading ? (
            <p className={styles.emptyText}>Loading...</p>
          ) : sessions.length === 0 ? (
            <p className={styles.emptyText}>
              {showArchived ? "No conversations yet" : "No active conversations"}
            </p>
          ) : (
            <>
              {sessions.filter((s) => !s.is_archived).map((session) => (
                <div
                  key={session.session_id}
                  className={`${styles.sessionItem} ${
                    activeSessionId === session.session_id ? styles.active : ""
                  }`}
                  onClick={() => onSelectSession(session.session_id)}
                >
                  {editingId === session.session_id ? (
                    <input
                      className={styles.renameInput}
                      value={editTitle}
                      onChange={(event) => setEditTitle(event.target.value)}
                      onBlur={() => handleFinishRename(session.session_id)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") handleFinishRename(session.session_id);
                        if (event.key === "Escape") setEditingId(null);
                      }}
                      onClick={(event) => event.stopPropagation()}
                      autoFocus
                    />
                  ) : (
                    <>
                      <ChatBubbleIcon className={styles.sessionIcon} width={14} height={14} />
                      <span className={styles.sessionTitle}>{session.title}</span>
                      <button
                        className={styles.quickDelete}
                        onClick={(event) => {
                          event.stopPropagation();
                          onDeleteSession(session.session_id);
                        }}
                        aria-label="Delete session"
                      >
                        <TrashIcon width={14} height={14} />
                      </button>
                      <DropdownMenu.Root>
                        <DropdownMenu.Trigger asChild>
                          <button
                            className={styles.menuTrigger}
                            onClick={(event) => event.stopPropagation()}
                            aria-label="Session options"
                          >
                            <DotsHorizontalIcon width={14} height={14} />
                          </button>
                        </DropdownMenu.Trigger>
                        <DropdownMenu.Portal>
                          <DropdownMenu.Content className={styles.dropdownContent} sideOffset={4} align="start">
                            <DropdownMenu.Item
                              className={styles.dropdownItem}
                              onSelect={() => handleStartRename(session.session_id, session.title)}
                            >
                              <Pencil1Icon width={14} height={14} />
                              Rename
                            </DropdownMenu.Item>
                            <DropdownMenu.Item
                              className={styles.dropdownItem}
                              onSelect={() => onArchiveSession(session.session_id)}
                            >
                              <ArchiveIcon width={14} height={14} />
                              Archive
                            </DropdownMenu.Item>
                            <DropdownMenu.Separator className={styles.dropdownSeparator} />
                            <DropdownMenu.Item
                              className={`${styles.dropdownItem} ${styles.destructive}`}
                              onSelect={() => onDeleteSession(session.session_id)}
                            >
                              <TrashIcon width={14} height={14} />
                              Delete
                            </DropdownMenu.Item>
                          </DropdownMenu.Content>
                        </DropdownMenu.Portal>
                      </DropdownMenu.Root>
                    </>
                  )}
                </div>
              ))}

              {showArchived && sessions.some((s) => s.is_archived) && (
                <>
                  <div className={styles.sectionLabel}>Archived</div>
                  {sessions.filter((s) => s.is_archived).map((session) => (
                    <div
                      key={session.session_id}
                      className={`${styles.sessionItem} ${styles.archived} ${
                        activeSessionId === session.session_id ? styles.active : ""
                      }`}
                      onClick={() => onSelectSession(session.session_id)}
                    >
                      <ArchiveIcon className={styles.sessionIcon} width={14} height={14} />
                      <span className={styles.sessionTitle}>{session.title}</span>
                      <button
                        className={styles.quickDelete}
                        onClick={(event) => {
                          event.stopPropagation();
                          onDeleteSession(session.session_id);
                        }}
                        aria-label="Delete session"
                      >
                        <TrashIcon width={14} height={14} />
                      </button>
                      <DropdownMenu.Root>
                        <DropdownMenu.Trigger asChild>
                          <button
                            className={styles.menuTrigger}
                            onClick={(event) => event.stopPropagation()}
                            aria-label="Session options"
                          >
                            <DotsHorizontalIcon width={14} height={14} />
                          </button>
                        </DropdownMenu.Trigger>
                        <DropdownMenu.Portal>
                          <DropdownMenu.Content className={styles.dropdownContent} sideOffset={4} align="start">
                            <DropdownMenu.Item
                              className={styles.dropdownItem}
                              onSelect={() => onUnarchiveSession(session.session_id)}
                            >
                              <ResetIcon width={14} height={14} />
                              Unarchive
                            </DropdownMenu.Item>
                            <DropdownMenu.Separator className={styles.dropdownSeparator} />
                            <DropdownMenu.Item
                              className={`${styles.dropdownItem} ${styles.destructive}`}
                              onSelect={() => onDeleteSession(session.session_id)}
                            >
                              <TrashIcon width={14} height={14} />
                              Delete
                            </DropdownMenu.Item>
                          </DropdownMenu.Content>
                        </DropdownMenu.Portal>
                      </DropdownMenu.Root>
                    </div>
                  ))}
                </>
              )}
            </>
          )}
        </nav>

        <div className={styles.footer}>
          <Tooltip.Root>
            <Tooltip.Trigger asChild>
              <button
                className={`${styles.footerButton} ${currentView === "performance" ? styles.footerButtonActive : ""}`}
                onClick={currentView === "performance" ? onNavigateChat : onNavigatePerformance}
                aria-label="Account Performance"
              >
                <StarIcon width={18} height={18} className={styles.footerIcon} />
                {isOpen && <span className={styles.footerLabel}>{currentView === "performance" ? "Back to Chat" : "Account Performance"}</span>}
              </button>
            </Tooltip.Trigger>
            <Tooltip.Content className={styles.tooltip} side="right" sideOffset={8}>
              {currentView === "performance" ? "Back to Chat" : "Account Performance"}
            </Tooltip.Content>
          </Tooltip.Root>

          <Tooltip.Root>
            <Tooltip.Trigger asChild>
              <button className={styles.footerButton} onClick={onToggleArchived} aria-label="Archived Chats">
                <ArchiveIcon width={18} height={18} className={styles.footerIcon} />
                {isOpen && <span className={styles.footerLabel}>{showArchived ? "Hide archived" : "Archived Chats"}</span>}
              </button>
            </Tooltip.Trigger>
            <Tooltip.Content className={styles.tooltip} side="right" sideOffset={8}>
              {showArchived ? "Hide archived" : "Show archived"}
            </Tooltip.Content>
          </Tooltip.Root>

          <Tooltip.Root>
            <Tooltip.Trigger asChild>
              <button className={styles.footerButton} onClick={theme.toggleTheme} aria-label="Toggle Theme">
                {theme.theme === "dark" ? <SunIcon width={18} height={18} className={styles.footerIcon} /> : <MoonIcon width={18} height={18} className={styles.footerIcon} />}
                {isOpen && <span className={styles.footerLabel}>{theme.theme === "dark" ? "Light Mode" : "Dark Mode"}</span>}
              </button>
            </Tooltip.Trigger>
            <Tooltip.Content className={styles.tooltip} side="right" sideOffset={8}>
              Help / Theme
            </Tooltip.Content>
          </Tooltip.Root>
        </div>
      </aside>
    </Tooltip.Provider>
  );
}
