import { useCallback, useRef, useState } from "react";

export interface PlanningStep {
  agent: string;
  task: string;
}

export interface ThinkingState {
  phase: "planning" | "executing" | "synthesizing" | "done" | "idle";
  reasoning?: string;
  steps?: PlanningStep[];
  completedSteps: CompletedStep[];
}

export interface CompletedStep {
  agent: string;
  result: string;
  stepIndex: number;
}

interface StreamCallbacks {
  onDone: (message: {
    message_id: string;
    session_id: string;
    role: string;
    content: string;
    metadata: Record<string, unknown> | null | undefined;
    context: Record<string, unknown> | null;
    created_at: string;
  }) => void;
  onError: () => void;
}

const EMPTY_THINKING_STATE: ThinkingState = {
  phase: "idle",
  completedSteps: [],
};

export function useMessageStream() {
  const [thinkingBySessionId, setThinkingBySessionId] = useState<Record<string, ThinkingState>>({});
  const [sendingBySessionId, setSendingBySessionId] = useState<Record<string, boolean>>({});
  const abortRefs = useRef(new Map<string, AbortController>());

  const sendStreaming = useCallback(
    async (
      sessionId: string,
      content: string,
      callbacks: StreamCallbacks,
      fileContext?: string,
      fileName?: string,
      fileType?: string,
      imageBase64?: string | null,
    ) => {
      abortRefs.current.get(sessionId)?.abort();
      const controller = new AbortController();
      abortRefs.current.set(sessionId, controller);

      setSendingBySessionId((prev) => ({ ...prev, [sessionId]: true }));
      setThinkingBySessionId((prev) => ({
        ...prev,
        [sessionId]: { phase: "planning", completedSteps: [] },
      }));

      const token = localStorage.getItem("access_token");
      const body: Record<string, string | null> = { content };
      if (fileContext) body.file_context = fileContext;
      if (fileName) body.file_name = fileName;
      if (fileType) body.file_type = fileType;
      if (imageBase64) body.image_base64 = imageBase64;

      const response = await fetch(`/api/chat/sessions/${sessionId}/messages/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        setSendingBySessionId((prev) => ({ ...prev, [sessionId]: false }));
        setThinkingBySessionId((prev) => ({ ...prev, [sessionId]: EMPTY_THINKING_STATE }));
        callbacks.onError();
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          let eventType = "";
          for (const line of lines) {
            if (line.startsWith("event: ")) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith("data: ") && eventType) {
              const data = JSON.parse(line.slice(6));
              handleEvent(
                eventType,
                data,
                sessionId,
                setThinkingBySessionId,
                setSendingBySessionId,
                callbacks,
              );
              eventType = "";
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setSendingBySessionId((prev) => ({ ...prev, [sessionId]: false }));
          setThinkingBySessionId((prev) => ({ ...prev, [sessionId]: EMPTY_THINKING_STATE }));
          callbacks.onError();
        }
      } finally {
        if (abortRefs.current.get(sessionId) === controller) {
          abortRefs.current.delete(sessionId);
        }
      }
    },
    [],
  );

  const resetSessionState = useCallback((sessionId: string) => {
    abortRefs.current.get(sessionId)?.abort();
    abortRefs.current.delete(sessionId);
    setSendingBySessionId((prev) => ({ ...prev, [sessionId]: false }));
    setThinkingBySessionId((prev) => ({ ...prev, [sessionId]: EMPTY_THINKING_STATE }));
  }, []);

  return {
    thinkingBySessionId,
    sendingBySessionId,
    sendStreaming,
    resetSessionState,
  };
}

function handleEvent(
  eventType: string,
  data: Record<string, unknown>,
  sessionId: string,
  setThinkingBySessionId: React.Dispatch<React.SetStateAction<Record<string, ThinkingState>>>,
  setSendingBySessionId: React.Dispatch<React.SetStateAction<Record<string, boolean>>>,
  callbacks: StreamCallbacks,
) {
  switch (eventType) {
    case "planning":
      setThinkingBySessionId((prev) => ({
        ...prev,
        [sessionId]: {
          phase: "planning",
          reasoning: data.reasoning as string,
          steps: data.steps as PlanningStep[],
          completedSteps: [],
        },
      }));
      break;

    case "agent_step":
      setThinkingBySessionId((prev) => {
        const current = prev[sessionId] ?? EMPTY_THINKING_STATE;
        return {
          ...prev,
          [sessionId]: {
            ...current,
            phase: "executing",
            completedSteps: [
              ...current.completedSteps,
              {
                agent: data.agent as string,
                result: data.result as string,
                stepIndex: data.step_index as number,
              },
            ],
          },
        };
      });
      break;

    case "synthesizing":
      setThinkingBySessionId((prev) => {
        const current = prev[sessionId] ?? EMPTY_THINKING_STATE;
        return {
          ...prev,
          [sessionId]: { ...current, phase: "synthesizing" },
        };
      });
      break;

    case "done":
      setThinkingBySessionId((prev) => {
        const current = prev[sessionId] ?? EMPTY_THINKING_STATE;
        return {
          ...prev,
          [sessionId]: { ...current, phase: "done" },
        };
      });
      setSendingBySessionId((prev) => ({ ...prev, [sessionId]: false }));
      callbacks.onDone(
        data.message as {
          message_id: string;
          session_id: string;
          role: string;
          content: string;
          metadata: Record<string, unknown> | null | undefined;
          context: Record<string, unknown> | null;
          created_at: string;
        },
      );
      break;
  }
}
