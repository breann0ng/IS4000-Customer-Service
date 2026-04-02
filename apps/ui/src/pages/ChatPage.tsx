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
import { PerformancePage } from "@/pages/PerformancePage";
import styles from "./ChatPage.module.css";

interface ChatPageProps {
  user: UserProfile;
  onLogout: () => void;
  theme: { theme: "light" | "dark"; toggleTheme: () => void };
  llmMode: "mock" | "live" | "unknown";
}

export function ChatPage({ user, onLogout, theme }: ChatPageProps) {
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessageResponse[]>([]);
  const [isLoadingSessions, setIsLoadingSessions] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sidebarWidth, setSidebarWidth] = useState(260);
  const [currentView, setCurrentView] = useState<"chat" | "performance">("chat");
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);
  const performanceSessionIdRef = useRef<string | null>(null);
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

  const handleSelectSession = useCallback(
    async (sessionId: string) => {
      // Reset any ongoing stream state when switching sessions
      setIsSending(false);
      resetThinking();
      setActiveSessionId(sessionId);
      try {
        const { data: session } = await getChatSessionApiChatSessionsSessionIdGet({
          throwOnError: true,
          path: { session_id: sessionId },
        });
        setMessages(session.messages ?? []);
      } catch (error) {
        console.error("Failed to fetch session:", error);
        setMessages([]);
      }
    },
    [resetThinking]
  );

  const handleNewSession = useCallback(async () => {
    setActiveSessionId(null);
    setMessages([]);
    try {
      const { data: session } = await createChatSessionApiChatSessionsPost({
        throwOnError: true,
        body: { title: "New Chat" },
      });
      setActiveSessionId(session.session_id);
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

  const handleAskFromPerformance = useCallback(async (question: string) => {
    setCurrentView("chat");

    // Reuse existing performance session if we have one
    if (performanceSessionIdRef.current) {
      // Switch to the performance session if not already active
      if (activeSessionId !== performanceSessionIdRef.current) {
        await handleSelectSession(performanceSessionIdRef.current);
      }
      setPendingQuestion(question);
      return;
    }

    // Create a dedicated session for performance questions
    try {
      const { data: session } = await createChatSessionApiChatSessionsPost({
        throwOnError: true,
        body: { title: "Account Performance Q&A" },
      });
      performanceSessionIdRef.current = session.session_id;
      setActiveSessionId(session.session_id);
      setMessages([]);
      await loadSessions();
      setPendingQuestion(question);
    } catch {
      /* session creation failed silently */
    }
  }, [activeSessionId, loadSessions, handleSelectSession]);

  // Send pending question once we have an active session
  useEffect(() => {
    if (pendingQuestion && activeSessionId && !isSending) {
      const question = pendingQuestion;
      setPendingQuestion(null);
      void handleSendMessage(question);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingQuestion, activeSessionId, isSending]);

  const handleSendMessage = useCallback(async (content: string) => {
    if (isSending) return;
    
    if (!activeSessionId) {
      setPendingQuestion(content);
      void handleNewSession();
      return;
    }

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
          metadata: message.metadata,
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
  }, [activeSessionId, isSending, loadSessions, handleNewSession, sendStreaming, resetThinking]);

  return (
    <div className={styles.layout}>
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        isLoading={isLoadingSessions}
        isOpen={sidebarOpen}
        showArchived={showArchived}
        theme={theme}
        currentView={currentView}
        onSelectSession={(id) => { setCurrentView("chat"); handleSelectSession(id); }}
        onNewSession={() => { setCurrentView("chat"); handleNewSession(); }}
        onDeleteSession={handleDeleteSession}
        onRenameSession={handleRenameSession}
        onArchiveSession={handleArchiveSession}
        onUnarchiveSession={handleUnarchiveSession}
        onToggleArchived={() => setShowArchived((prev) => !prev)}
        width={sidebarWidth}
        onWidthChange={setSidebarWidth}
        onToggle={() => setSidebarOpen((prev) => !prev)}
        onNavigatePerformance={() => setCurrentView("performance")}
        onNavigateChat={() => setCurrentView("chat")}
      />
      {currentView === "chat" ? (
        <ChatWindow
          messages={messages}
          isSending={isSending}
          thinking={thinking}
          sidebarOpen={sidebarOpen}
          user={user}
          onLogout={onLogout}
          onSendMessage={handleSendMessage}
          onToggleSidebar={() => setSidebarOpen((prev) => !prev)}
        />
      ) : (
        <PerformancePage
          onAskQuestion={handleAskFromPerformance}
          onBack={() => setCurrentView("chat")}
        />
      )}
    </div>
  );
}
