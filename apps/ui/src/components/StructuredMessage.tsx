import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChartCard, type ChartData } from "./ChartCard";
import styles from "./StructuredMessage.module.css";

// ─── Content Preprocessors ────────────────────────────────────────────────────

/**
 * The API sometimes returns markdown headings inline without surrounding
 * newlines, e.g. "...sentence. ### 1. Summary The next sentence..."
 * ReactMarkdown requires a blank line before ### to parse it as a heading.
 */
function normalisedHeadings(content: string): string {
  return content
    .replace(/([^\n])([ \t]*\n?[ \t]*)(#{1,6} )/g, "$1\n\n$3")
    .replace(/(#{1,6} [^\n]+)(\n?)([^\n#])/g, "$1\n\n$3");
}

/**
 * Extracts JSON chart objects from the content string.
 * Matches both fenced code blocks (```json { ... } ```) and bare JSON objects
 * with a "type" key of "pie" | "bar" | "line".
 * Returns the cleaned markdown text (charts stripped out) + parsed chart array.
 */
function extractCharts(raw: string): { text: string; charts: ChartData[] } {
  const charts: ChartData[] = [];

  // 1. Strip fenced ```json blocks that contain a chart object
  let text = raw.replace(/```json\s*(\{[\s\S]*?\})\s*```/g, (_match, jsonStr) => {
    try {
      const parsed = JSON.parse(jsonStr);
      if (isChartData(parsed)) {
        charts.push(parsed);
        return ""; // remove from markdown
      }
    } catch { /* not valid JSON, leave in place */ }
    return _match;
  });

  // 2. Strip bare JSON objects { "type": "pie"|"bar"|"line"|"gauge", ... } in text
  text = text.replace(/\{[\s\S]*?"type"\s*:\s*"(pie|bar|line|gauge)"[\s\S]*?\}/g, (match) => {
    try {
      const parsed = JSON.parse(match);
      if (isChartData(parsed)) {
        charts.push(parsed);
        return "";
      }
    } catch { /* malformed JSON — leave as-is */ }
    return match;
  });

  return { text: text.trim(), charts };
}

function isChartData(obj: unknown): obj is ChartData {
  if (typeof obj !== "object" || obj === null) return false;
  const o = obj as Record<string, unknown>;
  return (
    ["pie", "bar", "line", "gauge"].includes(o.type as string) &&
    typeof o.title === "string" &&
    Array.isArray(o.labels) &&
    Array.isArray(o.values)
  );
}

// ─── Types ────────────────────────────────────────────────────────────────────

export interface MetricItem {
  label: string;
  value: string;
  trend?: "up" | "down" | "neutral" | null;
}

interface StructuredMessageProps {
  content: string;
  metrics?: MetricItem[];
  suggestions?: string[];
  onSuggestionClick: (suggestion: string) => void;
}

// Section color themes cycling through 6 variants (accent = theme green)
const SECTION_COLORS = [
  "accent",  // green (primary)
  "blue",
  "teal",
  "indigo",
  "amber",
  "violet",
] as const;

let sectionColorIndex = 0;

// ─── Component ────────────────────────────────────────────────────────────────

export function StructuredMessage({
  content,
  metrics,
  suggestions,
  onSuggestionClick,
}: StructuredMessageProps) {
  sectionColorIndex = 0;

  const { text: cleanedText, charts } = extractCharts(content);
  const markdownText = normalisedHeadings(cleanedText);

  return (
    <div className={styles.structuredMessage}>

      {/* ── Metric Cards (from API metadata) ───────────────────── */}
      {metrics && metrics.length > 0 && (
        <div className={styles.metricGrid}>
          {metrics.map((metric, index) => (
            <div key={`${metric.label}-${index}`} className={styles.metricCard}>
              <span className={styles.metricLabel}>{metric.label}</span>
              <div className={styles.metricValueLine}>
                <span className={styles.metricValue}>{metric.value}</span>
                {metric.trend && (
                  <span
                    className={`${styles.metricTrend} ${
                      metric.trend === "up"
                        ? styles.up
                        : metric.trend === "down"
                        ? styles.down
                        : styles.neutral
                    }`}
                  >
                    {metric.trend === "up" ? "▲" : metric.trend === "down" ? "▼" : "━"}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Parsed Chart Cards ──────────────────────────────────── */}
      {charts.length > 0 && (
        <div className={styles.chartGrid}>
          {charts.map((chart, i) => (
            <ChartCard key={`chart-${i}`} data={chart} />
          ))}
        </div>
      )}

      {/* ── Main Markdown Content ───────────────────────────────── */}
      <div className={styles.markdownContent}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            // Section headers → colored card headers
            h3: ({ children, ...props }) => {
              const color = SECTION_COLORS[sectionColorIndex % SECTION_COLORS.length];
              sectionColorIndex++;
              return (
                <div className={`${styles.sectionCard} ${styles[`card_${color}`]}`}>
                  <div className={styles.sectionCardBar} />
                  <h3 className={styles.sectionHeader} {...props}>
                    {children}
                  </h3>
                </div>
              );
            },

            // Paragraphs
            p: ({ ...props }) => <p className={styles.paragraph} {...props} />,

            // Bold → boxed highlight for key metrics
            strong: ({ ...props }) => (
              <strong className={styles.boldHighlight} {...props} />
            ),

            // Ordered lists → numbered checklist style
            ol: ({ ...props }) => <ol className={styles.orderedList} {...props} />,
            li: ({ children, ...props }) => (
              <li className={styles.listItem} {...props}>
                {children}
              </li>
            ),

            // Unordered lists
            ul: ({ ...props }) => <ul className={styles.unorderedList} {...props} />,

            // Blockquote → summary callout
            blockquote: ({ ...props }) => (
              <blockquote className={styles.summaryCallout} {...props} />
            ),

            // Tables → styled table
            table: ({ ...props }) => (
              <div className={styles.tableWrapper}>
                <table className={styles.table} {...props} />
              </div>
            ),
            thead: ({ ...props }) => <thead className={styles.thead} {...props} />,
            th: ({ ...props }) => <th className={styles.th} {...props} />,
            td: ({ ...props }) => <td className={styles.td} {...props} />,
            tr: ({ ...props }) => <tr className={styles.tr} {...props} />,

            // Horizontal rule
            hr: () => <hr className={styles.sectionDivider} />,
          }}
        >
          {markdownText}
        </ReactMarkdown>
      </div>

      {/* ── Suggested Questions ─────────────────────────────────── */}
      {suggestions && suggestions.length > 0 && (
        <div className={styles.suggestionSection}>
          <div className={styles.suggestionHeader}>
            <svg
              width="14" height="14" viewBox="0 0 14 14" fill="none"
              className={styles.suggestionIcon}
            >
              <circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.5" />
              <path d="M7 4v4M7 9.5v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            <span className={styles.suggestionTitle}>You might also want to ask:</span>
          </div>
          <div className={styles.suggestionGrid}>
            {suggestions.map((suggestion, index) => (
              <button
                key={`${suggestion}-${index}`}
                className={styles.suggestionButton}
                onClick={() => onSuggestionClick(suggestion)}
              >
                <span>{suggestion}</span>
                <span className={styles.suggestionArrow}>›</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
