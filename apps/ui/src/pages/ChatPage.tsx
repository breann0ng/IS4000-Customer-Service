import { useCallback, useEffect, useRef, useState } from "react";
import type { UserProfile, ChatSessionSummary, ChatMessageResponse } from "@/api/generated";
import {
  createChatSessionApiChatSessionsPost,
  deleteChatSessionApiChatSessionsSessionIdDelete,
  getChatSessionApiChatSessionsSessionIdGet,
  listChatSessionsApiChatSessionsGet,
  updateChatSessionApiChatSessionsSessionIdPatch,
} from "@/api/generated";
import { useMessageStream } from "@/hooks/useMessageStream";
import { Sidebar } from "@/components/Sidebar";
import { ChatWindow } from "@/components/ChatWindow";
import styles from "./ChatPage.module.css";

interface ChatPageProps {
  user: UserProfile;
  onLogout: () => void;
  theme: { theme: "light" | "dark"; toggleTheme: () => void };
  llmMode: "mock" | "live" | "unknown";
}

export function ChatPage({ user, onLogout, theme, llmMode }: ChatPageProps) {
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessageResponse[]>([]);
  const [isLoadingSessions, setIsLoadingSessions] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const { thinking, sendStreaming, resetThinking } = useMessageStream();
  const [showArchived, setShowArchived] = useState(false);
  const showArchivedRef = useRef(showArchived);
  showArchivedRef.current = showArchived;

  const loadSessions = useCallback(async () => {
    try {
      const { data } = await listChatSessionsApiChatSessionsGet({
        throwOnError: true,
        query: { include_archived: showArchivedRef.current },
      });
      setSessions(data);
    } catch {
      /* session list load failed silently */
    } finally {
      setIsLoadingSessions(false);
    }
  }, []);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions, showArchived]);

  const handleSelectSession = useCallback(async (sessionId: string) => {
    setActiveSessionId(sessionId);
    try {
      const { data: session } = await getChatSessionApiChatSessionsSessionIdGet({
        throwOnError: true,
        path: { session_id: sessionId },
      });
      setMessages(session.messages ?? []);
    } catch {
      setMessages([]);
    }
  }, []);

  const handleNewSession = useCallback(async () => {
    try {
      const { data: session } = await createChatSessionApiChatSessionsPost({
        throwOnError: true,
        body: { title: "New Chat" },
      });
      setActiveSessionId(session.session_id);
      setMessages([]);
      await loadSessions();
    } catch {
      /* session creation failed silently */
    }
  }, [loadSessions]);

  const handleDeleteSession = useCallback(async (sessionId: string) => {
    try {
      await deleteChatSessionApiChatSessionsSessionIdDelete({
        throwOnError: true,
        path: { session_id: sessionId },
      });
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
        setMessages([]);
      }
      await loadSessions();
    } catch {
      /* session deletion failed silently */
    }
  }, [activeSessionId, loadSessions]);

  const handleRenameSession = useCallback(async (sessionId: string, title: string) => {
    try {
      await updateChatSessionApiChatSessionsSessionIdPatch({
        throwOnError: true,
        path: { session_id: sessionId },
        body: { title },
      });
      await loadSessions();
    } catch {
      /* rename failed silently */
    }
  }, [loadSessions]);

  const handleArchiveSession = useCallback(async (sessionId: string) => {
    try {
      await updateChatSessionApiChatSessionsSessionIdPatch({
        throwOnError: true,
        path: { session_id: sessionId },
        body: { is_archived: true },
      });
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
        setMessages([]);
      }
      await loadSessions();
    } catch {
      /* archive failed silently */
    }
  }, [activeSessionId, loadSessions]);

  const handleUnarchiveSession = useCallback(async (sessionId: string) => {
    try {
      await updateChatSessionApiChatSessionsSessionIdPatch({
        throwOnError: true,
        path: { session_id: sessionId },
        body: { is_archived: false },
      });
      await loadSessions();
    } catch {
      /* unarchive failed silently */
    }
  }, [loadSessions]);

  const handleSendMessage = useCallback(async (content: string) => {
    if (!activeSessionId || isSending) return;

    const userMessage: ChatMessageResponse = {
      message_id: crypto.randomUUID(),
      session_id: activeSessionId,
      role: "user",
      content,
      context: null,
      created_at: new Date().toISOString(),
    };

    setMessages((previous) => [...previous, userMessage]);
    setIsSending(true);

    await sendStreaming(activeSessionId, content, {
      onDone: (message) => {
        setMessages((previous) => [...previous, {
          message_id: message.message_id,
          session_id: message.session_id,
          role: message.role,
          content: message.content,
          context: message.context,
          created_at: message.created_at,
        }]);
        setIsSending(false);
        resetThinking();
        void loadSessions();
      },
      onError: () => {
        const errorMessage: ChatMessageResponse = {
          message_id: crypto.randomUUID(),
          session_id: activeSessionId,
          role: "assistant",
          content: "Sorry, something went wrong. Please try again.",
          context: null,
          created_at: new Date().toISOString(),
        };
        setMessages((previous) => [...previous, errorMessage]);
        setIsSending(false);
        resetThinking();
      },
    });
  }, [activeSessionId, isSending, loadSessions, sendStreaming, resetThinking]);

  return (
    <div className={styles.layout}>
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        isLoading={isLoadingSessions}
        isOpen={sidebarOpen}
        showArchived={showArchived}
        user={user}
        theme={theme}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
        onRenameSession={handleRenameSession}
        onArchiveSession={handleArchiveSession}
        onUnarchiveSession={handleUnarchiveSession}
        onToggleArchived={() => setShowArchived((prev) => !prev)}
        onLogout={onLogout}
        onToggle={() => setSidebarOpen((prev) => !prev)}
      />
      <ChatWindow
        messages={messages}
        isSending={isSending}
        thinking={thinking}
        hasActiveSession={activeSessionId !== null}
        sidebarOpen={sidebarOpen}
        llmMode={llmMode}
        onSendMessage={handleSendMessage}
        onNewSession={handleNewSession}
        onToggleSidebar={() => setSidebarOpen((prev) => !prev)}
      />
    </div>
  );
}
