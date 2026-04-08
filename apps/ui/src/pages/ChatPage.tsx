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
import { useFileUpload } from "@/hooks/useFileUpload";
import type { ThinkingState } from "@/hooks/useMessageStream";
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
  const [messagesBySessionId, setMessagesBySessionId] = useState<Record<string, ChatMessageResponse[]>>({});
  const [isLoadingSessions, setIsLoadingSessions] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sidebarWidth, setSidebarWidth] = useState(260);
  const [currentView, setCurrentView] = useState<"chat" | "performance">("chat");
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);
  const pendingFileDataRef = useRef<{ fileContext?: string; fileName?: string; imageBase64?: string | null; fileType?: string } | undefined>(undefined);
  const performanceSessionIdRef = useRef<string | null>(null);
  const {
    thinkingBySessionId,
    sendingBySessionId,
    sendStreaming,
    resetSessionState,
  } = useMessageStream();
  const { attachment, uploadFile, clearAttachment } = useFileUpload();
  const [showArchived, setShowArchived] = useState(false);
  const showArchivedRef = useRef(showArchived);
  showArchivedRef.current = showArchived;

  const emptyThinking: ThinkingState = {
    phase: "idle",
    completedSteps: [],
  };

  const activeMessages = activeSessionId ? (messagesBySessionId[activeSessionId] ?? []) : [];
  const activeThinking = activeSessionId ? thinkingBySessionId[activeSessionId] ?? emptyThinking : emptyThinking;
  const activeIsSending = activeSessionId ? Boolean(sendingBySessionId[activeSessionId]) : false;

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
      setMessagesBySessionId((prev) => ({
        ...prev,
        [sessionId]: session.messages ?? [],
      }));
    } catch {
      setMessagesBySessionId((prev) => ({
        ...prev,
        [sessionId]: [],
      }));
    }
  }, []);

  const handleNewSession = useCallback(async () => {
    try {
      const { data: session } = await createChatSessionApiChatSessionsPost({
        throwOnError: true,
        body: { title: "New Chat" },
      });
      setActiveSessionId(session.session_id);
      setMessagesBySessionId((prev) => ({
        ...prev,
        [session.session_id]: [],
      }));
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
      }
      setMessagesBySessionId((prev) => {
        const next = { ...prev };
        delete next[sessionId];
        return next;
      });
      resetSessionState(sessionId);
      await loadSessions();
    } catch {
      /* session deletion failed silently */
    }
  }, [activeSessionId, loadSessions, resetSessionState]);

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
      }
      resetSessionState(sessionId);
      await loadSessions();
    } catch {
      /* archive failed silently */
    }
  }, [activeSessionId, loadSessions, resetSessionState]);

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
      setMessagesBySessionId((prev) => ({
        ...prev,
        [session.session_id]: [],
      }));
      await loadSessions();
      setPendingQuestion(question);
    } catch {
      /* session creation failed silently */
    }
  }, [activeSessionId, loadSessions, handleSelectSession]);

  // Send pending question once we have an active session
  useEffect(() => {
    if (pendingQuestion && activeSessionId && !activeIsSending) {
      const question = pendingQuestion;
      const fileData = pendingFileDataRef.current;
      setPendingQuestion(null);
      pendingFileDataRef.current = undefined;
      void handleSendMessage(question, fileData);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingQuestion, activeSessionId, activeIsSending]);

  const handleSendMessage = useCallback(async (
    content: string,
    fileData?: { fileContext?: string; fileName?: string; imageBase64?: string | null; fileType?: string },
  ) => {
    const targetSessionId = activeSessionId;
    if (targetSessionId && sendingBySessionId[targetSessionId]) return;

    if (!targetSessionId) {
      setPendingQuestion(content);
      pendingFileDataRef.current = fileData;
      void handleNewSession();
      return;
    }

    const fileName = fileData?.fileName;
    const fileContext = fileData?.fileContext;
    const isImage = fileData?.imageBase64 != null;

    const userMessage: ChatMessageResponse = {
      message_id: crypto.randomUUID(),
      session_id: targetSessionId,
      role: "user",
      content,
      context: fileName
        ? {
            attached_file: fileName,
            file_type: fileData?.fileType ?? null,
            ...(isImage ? { image_base64: fileData.imageBase64 } : {}),
          }
        : null,
      created_at: new Date().toISOString(),
    };

    setMessagesBySessionId((previous) => ({
      ...previous,
      [targetSessionId]: [...(previous[targetSessionId] ?? []), userMessage],
    }));

    await sendStreaming(targetSessionId, content, {
      onDone: (message) => {
        setMessagesBySessionId((previous) => ({
          ...previous,
          [message.session_id]: [
            ...(previous[message.session_id] ?? []),
            {
              message_id: message.message_id,
              session_id: message.session_id,
              role: message.role,
              content: message.content,
              metadata: message.metadata,
              context: message.context,
              created_at: message.created_at,
            },
          ],
        }));
        void loadSessions();
      },
      onError: () => {
        const errorMessage: ChatMessageResponse = {
          message_id: crypto.randomUUID(),
          session_id: targetSessionId,
          role: "assistant",
          content: "Sorry, something went wrong. Please try again.",
          context: null,
          created_at: new Date().toISOString(),
        };
        setMessagesBySessionId((previous) => ({
          ...previous,
          [targetSessionId]: [...(previous[targetSessionId] ?? []), errorMessage],
        }));
      },
    }, fileContext, fileName, fileData?.fileType, fileData?.imageBase64);
  }, [activeSessionId, sendingBySessionId, loadSessions, handleNewSession, sendStreaming]);

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
        onNewSession={() => { setCurrentView("chat"); setActiveSessionId(null); void handleNewSession(); }}
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
          messages={activeMessages}
          isSending={activeIsSending}
          thinking={activeThinking}
          sidebarOpen={sidebarOpen}
          user={user}
          attachment={attachment}
          onLogout={onLogout}
          onSendMessage={handleSendMessage}
          onToggleSidebar={() => setSidebarOpen((prev) => !prev)}
          onFileSelect={uploadFile}
          onClearAttachment={clearAttachment}
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
