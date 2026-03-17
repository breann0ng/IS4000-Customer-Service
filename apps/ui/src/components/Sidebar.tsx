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
  SunIcon,
  MoonIcon,
  ExitIcon,
  ChatBubbleIcon,
  ChevronLeftIcon,
} from "@radix-ui/react-icons";
import type { ChatSessionSummary, UserProfile } from "@/api/generated";
import styles from "./Sidebar.module.css";

interface SidebarProps {
  sessions: ChatSessionSummary[];
  activeSessionId: string | null;
  isLoading: boolean;
  isOpen: boolean;
  showArchived: boolean;
  user: UserProfile;
  theme: { theme: "light" | "dark"; toggleTheme: () => void };
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
  onDeleteSession: (sessionId: string) => void;
  onRenameSession: (sessionId: string, title: string) => void;
  onArchiveSession: (sessionId: string) => void;
  onUnarchiveSession: (sessionId: string) => void;
  onToggleArchived: () => void;
  onLogout: () => void;
  onToggle: () => void;
}

export function Sidebar({
  sessions,
  activeSessionId,
  isLoading,
  isOpen,
  showArchived,
  user,
  theme,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  onRenameSession,
  onArchiveSession,
  onUnarchiveSession,
  onToggleArchived,
  onLogout,
  onToggle,
}: SidebarProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");

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

  return (
    <Tooltip.Provider delayDuration={300}>
      <aside className={`${styles.sidebar} ${isOpen ? styles.open : styles.closed}`}>
        <div className={styles.header}>
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

          <Tooltip.Root>
            <Tooltip.Trigger asChild>
              <button className={styles.iconButton} onClick={onToggle} aria-label="Close sidebar">
                <ChevronLeftIcon width={18} height={18} />
              </button>
            </Tooltip.Trigger>
            <Tooltip.Content className={styles.tooltip} side="right" sideOffset={8}>
              Close sidebar
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
          <button className={styles.footerButton} onClick={onToggleArchived}>
            <ArchiveIcon width={15} height={15} />
            <span>{showArchived ? "Hide archived" : "Show archived"}</span>
          </button>
          <button className={styles.footerButton} onClick={theme.toggleTheme}>
            {theme.theme === "dark" ? <SunIcon width={15} height={15} /> : <MoonIcon width={15} height={15} />}
            <span>{theme.theme === "dark" ? "Light mode" : "Dark mode"}</span>
          </button>
          <div className={styles.separator} />
          <div className={styles.userRow}>
            <div className={styles.avatar}>
              {user.display_name.charAt(0).toUpperCase()}
            </div>
            <span className={styles.userName}>{user.display_name}</span>
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
          </div>
        </div>
      </aside>
    </Tooltip.Provider>
  );
}
