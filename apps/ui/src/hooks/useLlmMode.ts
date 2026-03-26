import { useEffect, useState } from "react";

type LlmMode = "mock" | "live" | "unknown";

export function useLlmMode(): LlmMode {
  const [mode, setMode] = useState<LlmMode>("unknown");

  useEffect(() => {
    fetch("/api/health")
      .then((res) => res.json())
      .then((data: { llm_mode?: string }) => {
        if (data.llm_mode === "mock" || data.llm_mode === "live") {
          setMode(data.llm_mode);
        }
      })
      .catch(() => {
        /* health check failed */
      });
  }, []);

  return mode;
}
