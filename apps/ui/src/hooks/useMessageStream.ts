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
    context: Record<string, unknown> | null;
    created_at: string;
  }) => void;
  onError: () => void;
}

export function useMessageStream() {
  const [thinking, setThinking] = useState<ThinkingState>({
    phase: "idle",
    completedSteps: [],
  });
  const abortRef = useRef<AbortController | null>(null);

  const sendStreaming = useCallback(
    async (sessionId: string, content: string, callbacks: StreamCallbacks) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setThinking({ phase: "planning", completedSteps: [] });

      const token = localStorage.getItem("access_token");
      const response = await fetch(`/api/chat/sessions/${sessionId}/messages/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ content }),
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        setThinking({ phase: "idle", completedSteps: [] });
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
              handleEvent(eventType, data, setThinking, callbacks);
              eventType = "";
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setThinking({ phase: "idle", completedSteps: [] });
          callbacks.onError();
        }
      }
    },
    [],
  );

  const resetThinking = useCallback(() => {
    setThinking({ phase: "idle", completedSteps: [] });
  }, []);

  return { thinking, sendStreaming, resetThinking };
}

function handleEvent(
  eventType: string,
  data: Record<string, unknown>,
  setThinking: React.Dispatch<React.SetStateAction<ThinkingState>>,
  callbacks: StreamCallbacks,
) {
  switch (eventType) {
    case "planning":
      setThinking((prev) => ({
        ...prev,
        phase: "planning",
        reasoning: data.reasoning as string,
        steps: data.steps as PlanningStep[],
      }));
      break;

    case "agent_step":
      setThinking((prev) => ({
        ...prev,
        phase: "executing",
        completedSteps: [
          ...prev.completedSteps,
          {
            agent: data.agent as string,
            result: data.result as string,
            stepIndex: data.step_index as number,
          },
        ],
      }));
      break;

    case "synthesizing":
      setThinking((prev) => ({ ...prev, phase: "synthesizing" }));
      break;

    case "done":
      setThinking({ phase: "done", completedSteps: [] });
      callbacks.onDone(
        data.message as {
          message_id: string;
          session_id: string;
          role: string;
          content: string;
          context: Record<string, unknown> | null;
          created_at: string;
        },
      );
      break;
  }
}
