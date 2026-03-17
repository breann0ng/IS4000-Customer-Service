import { useState } from "react";
import { ChevronDownIcon, ChevronRightIcon, CheckCircledIcon, CircleIcon, GearIcon } from "@radix-ui/react-icons";
import type { ThinkingState } from "@/hooks/useMessageStream";
import styles from "./ThinkingIndicator.module.css";

const AGENT_LABELS: Record<string, string> = {
  wealth_advisory: "Wealth Advisory",
  private_banking: "Private Banking",
  client_services: "Client Services",
  lending_credit: "Lending & Credit",
  compliance_tax: "Compliance & Tax",
  fx_treasury: "FX & Treasury",
};

interface ThinkingIndicatorProps {
  thinking: ThinkingState;
}

export function ThinkingIndicator({ thinking }: ThinkingIndicatorProps) {
  const [expanded, setExpanded] = useState(true);

  if (thinking.phase === "idle" || thinking.phase === "done") return null;

  return (
    <div className={styles.container}>
      <div className={styles.avatar}>
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <rect width="20" height="20" rx="4" fill="var(--color-accent)" />
          <path d="M6 10h8M10 6v8" stroke="white" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </div>
      <div className={styles.content}>
        <button className={styles.toggle} onClick={() => setExpanded((prev) => !prev)}>
          <span className={styles.spinner} />
          <span className={styles.phaseLabel}>{phaseLabel(thinking)}</span>
          {expanded
            ? <ChevronDownIcon width={14} height={14} />
            : <ChevronRightIcon width={14} height={14} />
          }
        </button>

        {expanded && (
          <div className={styles.steps}>
            {thinking.phase === "planning" && thinking.reasoning && (
              <div className={styles.step}>
                <GearIcon className={styles.stepIconActive} width={13} height={13} />
                <span className={styles.stepText}>{thinking.reasoning}</span>
              </div>
            )}

            {thinking.steps && thinking.steps.map((step, index) => {
              const completed = thinking.completedSteps.some((c) => c.agent === step.agent);
              const isActive = !completed && thinking.phase === "executing" &&
                index === thinking.completedSteps.length;

              return (
                <div key={index} className={styles.step}>
                  {completed ? (
                    <CheckCircledIcon className={styles.stepIconDone} width={13} height={13} />
                  ) : isActive ? (
                    <span className={styles.stepSpinner} />
                  ) : (
                    <CircleIcon className={styles.stepIconPending} width={13} height={13} />
                  )}
                  <span className={`${styles.stepText} ${completed ? styles.stepDone : ""}`}>
                    {AGENT_LABELS[step.agent] ?? step.agent}: {step.task}
                  </span>
                </div>
              );
            })}

            {thinking.completedSteps.map((step, index) => (
              <div key={`result-${index}`} className={styles.stepResult}>
                <span className={styles.resultLabel}>{AGENT_LABELS[step.agent] ?? step.agent}:</span>
                <span className={styles.resultText}>
                  {step.result.length > 150 ? `${step.result.slice(0, 150)}...` : step.result}
                </span>
              </div>
            ))}

            {thinking.phase === "synthesizing" && (
              <div className={styles.step}>
                <span className={styles.stepSpinner} />
                <span className={styles.stepText}>Composing final response...</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function phaseLabel(thinking: ThinkingState): string {
  switch (thinking.phase) {
    case "planning": return "Analyzing your request...";
    case "executing": {
      const total = thinking.steps?.length ?? 0;
      const done = thinking.completedSteps.length;
      return `Working... (${done}/${total} steps)`;
    }
    case "synthesizing": return "Preparing response...";
    default: return "Thinking...";
  }
}
