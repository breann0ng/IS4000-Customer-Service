import { useEffect, useRef, useState, useCallback } from "react";
import styles from "./PerformancePage.module.css";

interface PerformanceData {
  portfolio_current_value: number;
  portfolio_value: { month: string; value: number }[];
  asset_allocation: { label: string; value: number; color?: string }[];
  monthly_returns: { month: string; value: number }[];
  return_metrics: {
    six_month_return_pct: number;
    ytd_return_pct: number;
    one_year_return_pct: number;
  };
  risk_metrics: {
    risk_profile: string;
    sharpe_ratio: number;
    volatility_pct: number;
  };
  benchmark_name: string;
  relationship_manager: {
    name: string;
    email: string;
    phone: string;
  };
  benchmark_comparison: { month: string; portfolio: number; benchmark: number }[];
  net_worth: {
    asOf: string;
    customer: string;
    customerId: string;
    assets: {
      liquidAssets: { label: string; value: number; note: string }[];
      investmentPortfolio: { label: string; value: number; note?: string }[];
      realEstate: { label: string; value: number; note: string }[];
      otherAssets: { label: string; value: number; note: string }[];
    };
    liabilities: { label: string; value: number; note: string; rate?: string }[];
  };
  insights: any[];
}

interface PerformancePageProps {
  onAskQuestion: (question: string) => void;
  onBack: () => void;
}

// Colors for asset allocation if not provided by API
const ALLOCATION_COLORS = ["#da291c", "#1e1e1e", "#ffd100", "#9b1318", "#b6b6b6", "#888888"];

function toNumber(value: unknown, fallback = 0): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function normalizePerformanceData(raw: any): PerformanceData {
  const portfolioValue = Array.isArray(raw?.portfolio_value)
    ? raw.portfolio_value.map((entry: any) => ({
        month: String(entry?.month ?? ""),
        value: toNumber(entry?.value),
      }))
    : [];

  const monthlyReturns: { month: string; value: number }[] = Array.isArray(raw?.monthly_returns)
    ? raw.monthly_returns.map((entry: any) => ({
        month: String(entry?.month ?? ""),
        value: toNumber(entry?.value),
      }))
    : [];

  const sixMonthFallback = monthlyReturns
    .slice(-6)
    .reduce((acc: number, entry: { value: number }) => acc * (1 + entry.value / 100), 1);

  const returnsByMonth = new Map(monthlyReturns.map((entry) => [entry.month, entry.value]));

  const benchmarkComparison = Array.isArray(raw?.benchmark_comparison)
    ? raw.benchmark_comparison.map((entry: any) => {
        const month = String(entry?.month ?? "");
        const hasPortfolioAndBenchmark =
          entry && typeof entry === "object" && "portfolio" in entry && "benchmark" in entry;

        if (hasPortfolioAndBenchmark) {
          return {
            month,
            portfolio: toNumber(entry?.portfolio),
            benchmark: toNumber(entry?.benchmark),
          };
        }

        return {
          month,
          portfolio: toNumber(returnsByMonth.get(month), 0),
          benchmark: toNumber(entry?.value, 0),
        };
      })
    : [];

  const assets = raw?.net_worth?.assets ?? {};

  const insights = Array.isArray(raw?.insights)
    ? raw.insights.map((signal: any, index: number) => ({
        id: String(signal?.id ?? `insight-${index + 1}`),
        priority:
          signal?.priority === "high" || signal?.priority === "medium" || signal?.priority === "low"
            ? signal.priority
            : "medium",
        category: String(signal?.category ?? "General"),
        icon: String(signal?.icon ?? "💡"),
        title: String(signal?.title ?? "Insight"),
        trigger: String(signal?.trigger ?? "Portfolio activity signal"),
        summary: String(signal?.summary ?? "No summary available."),
        suggested_actions: Array.isArray(signal?.suggested_actions)
          ? signal.suggested_actions.map((action: any) => String(action))
          : [],
        rm_context: String(signal?.rm_context ?? signal?.summary ?? ""),
        tags: Array.isArray(signal?.tags) ? signal.tags.map((tag: any) => String(tag)) : [],
      }))
    : [];

  return {
    portfolio_current_value: toNumber(raw?.portfolio_current_value),
    portfolio_value: portfolioValue,
    asset_allocation: Array.isArray(raw?.asset_allocation)
      ? raw.asset_allocation.map((entry: any) => ({
          label: String(entry?.label ?? "Unknown"),
          value: toNumber(entry?.value),
          color: entry?.color,
        }))
      : [],
    monthly_returns: monthlyReturns,
    return_metrics: {
      six_month_return_pct: toNumber(raw?.return_metrics?.six_month_return_pct, (sixMonthFallback - 1) * 100),
      ytd_return_pct: toNumber(raw?.return_metrics?.ytd_return_pct),
      one_year_return_pct: toNumber(raw?.return_metrics?.one_year_return_pct),
    },
    risk_metrics: {
      risk_profile: String(raw?.risk_metrics?.risk_profile ?? "N/A"),
      sharpe_ratio: toNumber(raw?.risk_metrics?.sharpe_ratio),
      volatility_pct: toNumber(raw?.risk_metrics?.volatility_pct),
    },
    benchmark_name: String(raw?.benchmark_name ?? "Benchmark"),
    relationship_manager: {
      name: String(raw?.relationship_manager?.name ?? "Relationship Manager"),
      email: String(raw?.relationship_manager?.email ?? ""),
      phone: String(raw?.relationship_manager?.phone ?? ""),
    },
    benchmark_comparison: benchmarkComparison,
    net_worth: {
      asOf: String(raw?.net_worth?.asOf ?? ""),
      customer: String(raw?.net_worth?.customer ?? "Client"),
      customerId: String(raw?.net_worth?.customerId ?? ""),
      assets: {
        liquidAssets: Array.isArray(assets?.liquidAssets)
          ? assets.liquidAssets.map((entry: any) => ({
              label: String(entry?.label ?? ""),
              value: toNumber(entry?.value),
              note: String(entry?.note ?? ""),
            }))
          : [],
        investmentPortfolio: Array.isArray(assets?.investmentPortfolio)
          ? assets.investmentPortfolio.map((entry: any) => ({
              label: String(entry?.label ?? ""),
              value: toNumber(entry?.value),
              note: entry?.note,
            }))
          : [],
        realEstate: Array.isArray(assets?.realEstate)
          ? assets.realEstate.map((entry: any) => ({
              label: String(entry?.label ?? ""),
              value: toNumber(entry?.value),
              note: String(entry?.note ?? ""),
            }))
          : [],
        otherAssets: Array.isArray(assets?.otherAssets)
          ? assets.otherAssets.map((entry: any) => ({
              label: String(entry?.label ?? ""),
              value: toNumber(entry?.value),
              note: String(entry?.note ?? ""),
            }))
          : [],
      },
      liabilities: Array.isArray(raw?.net_worth?.liabilities)
        ? raw.net_worth.liabilities.map((entry: any) => ({
            label: String(entry?.label ?? ""),
            value: toNumber(entry?.value),
            note: String(entry?.note ?? ""),
            rate: entry?.rate,
          }))
        : [],
    },
    insights,
  };
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function pieSlicePath(cx: number, cy: number, r: number, startAngle: number, endAngle: number) {
  const start = polarToCartesian(cx, cy, r, endAngle);
  const end = polarToCartesian(cx, cy, r, startAngle);
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;
  return `M ${cx} ${cy} L ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 0 ${end.x} ${end.y} Z`;
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-SG", { style: "currency", currency: "SGD", maximumFractionDigits: 0 }).format(value);
}

// ─── Question Input Panel ────────────────────────────────────────────────────

interface QuestionPanelProps {
  context: string;
  suggestedQuestion: string;
  onSend: (question: string) => void;
  onDismiss: () => void;
}

function QuestionPanel({ context, suggestedQuestion, onSend, onDismiss }: QuestionPanelProps) {
  const [question, setQuestion] = useState(suggestedQuestion);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  function handleSend() {
    const trimmed = question.trim();
    if (trimmed) {
      onSend(trimmed);
    }
  }

  return (
    <div className={styles.questionPanel}>
      <div className={styles.questionContext}>
        <span className={styles.questionContextIcon}>
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5" />
            <path d="M8 5v3M8 10.5v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </span>
        <span>{context}</span>
        <button className={styles.questionDismiss} onClick={onDismiss} aria-label="Dismiss">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
            <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>
      </div>
      <div className={styles.questionInputRow}>
        <textarea
          ref={inputRef}
          className={styles.questionInput}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
            if (e.key === "Escape") onDismiss();
          }}
          placeholder="Type your question..."
          rows={2}
          autoFocus
        />
        <button
          className={styles.questionSendButton}
          onClick={handleSend}
          disabled={!question.trim()}
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M2 8h12M10 4l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Ask
        </button>
      </div>
    </div>
  );
}

// ─── Net Worth Calculator ────────────────────────────────────────────────────

function NetWorthCalculator({ 
  data, 
  onAskQuestion 
}: { 
  data: PerformanceData["net_worth"];
  onAskQuestion: (context: string, suggestion: string) => void 
}) {
  const [expandedSection, setExpandedSection] = useState<string | null>(null);

  const totalLiquid = data.assets.liquidAssets.reduce((s: number, a: any) => s + a.value, 0);
  const totalPortfolio = data.assets.investmentPortfolio.reduce((s: number, a: any) => s + a.value, 0);
  const totalRealEstate = data.assets.realEstate.reduce((s: number, a: any) => s + a.value, 0);
  const totalOther = data.assets.otherAssets.reduce((s: number, a: any) => s + a.value, 0);
  const totalAssets = totalLiquid + totalPortfolio + totalRealEstate + totalOther;
  const totalLiabilities = data.liabilities.reduce((s: number, l: any) => s + Math.abs(l.value), 0);
  const netWorth = totalAssets - totalLiabilities;

  const assetSections = [
    {
      key: "liquid",
      label: "Liquid & Cash Assets",
      total: totalLiquid,
      color: "#da291c",
      items: data.assets.liquidAssets,
      icon: "💵",
      question: `My total liquid and cash assets are ${formatCurrency(totalLiquid)}. How does this liquidity position compare to what you'd recommend for someone with my profile?`,
    },
    {
      key: "portfolio",
      label: "Investment Portfolio (AUM)",
      total: totalPortfolio,
      color: "#1e1e1e",
      items: data.assets.investmentPortfolio,
      icon: "📈",
      question: `My investment portfolio with UBS is valued at ${formatCurrency(totalPortfolio)}. Can you give me a quick assessment of my current allocation and any rebalancing opportunities?`,
    },
    {
      key: "realestate",
      label: "Real Estate",
      total: totalRealEstate,
      color: "#9b1318",
      items: data.assets.realEstate,
      icon: "🏢",
      question: `My real estate holdings total ${formatCurrency(totalRealEstate)} across Singapore and Japan. What are your thoughts on my real estate exposure as a proportion of my net worth?`,
    },
    {
      key: "other",
      label: "Business & Other Assets",
      total: totalOther,
      color: "#ffd100",
      items: data.assets.otherAssets,
      icon: "🏛️",
      question: `I have ${formatCurrency(totalOther)} in business equity and other assets. What strategies would you recommend to optimise or diversify this part of my wealth?`,
    },
  ];

  // Bar widths: proportion of totalAssets
  function pct(val: number) { return Math.round((val / totalAssets) * 100); }

  return (
    <div className={styles.netWorthCard}>
      {/* ── Header ── */}
      <div className={styles.netWorthHeader}>
        <div>
          <h3 className={styles.netWorthTitle}>Net Worth Snapshot</h3>
          <p className={styles.netWorthSubtitle}>
            Client: {data.customer} ({data.customerId}) · As of {data.asOf} · All values in SGD
          </p>
        </div>
        <button
          className={styles.netWorthAskBtn}
          onClick={() => onAskQuestion(
            `Net worth: ${formatCurrency(netWorth)}`,
            `My current net worth is approximately ${formatCurrency(netWorth)}. Can you provide a comprehensive assessment of my financial position and suggest estate planning or wealth optimisation strategies?`,
          )}
        >
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
            <path d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 3v4m0 2.5v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          Ask Advisor
        </button>
      </div>

      {/* ── KPI Row ── */}
      <div className={styles.nwKpis}>
        <div className={styles.nwKpi}>
          <span className={styles.nwKpiLabel}>Total Assets</span>
          <span className={styles.nwKpiValue} style={{ color: "var(--color-text-primary)" }}>{formatCurrency(totalAssets)}</span>
        </div>
        <div className={styles.nwKpiDivider} />
        <div className={styles.nwKpi}>
          <span className={styles.nwKpiLabel}>Total Liabilities</span>
          <span className={styles.nwKpiValue} style={{ color: "#da291c" }}>−{formatCurrency(totalLiabilities)}</span>
        </div>
        <div className={styles.nwKpiDivider} />
        <div className={styles.nwKpi}>
          <span className={styles.nwKpiLabel}>Net Worth</span>
          <span className={styles.nwKpiValue} style={{ color: "#16a34a", fontWeight: 800 }}>{formatCurrency(netWorth)}</span>
        </div>
      </div>

      {/* ── Stacked bar ── */}
      <div className={styles.nwBar}>
        {assetSections.map((s) => (
          <div
            key={s.key}
            className={styles.nwBarSegment}
            style={{ width: `${pct(s.total)}%`, background: s.color }}
            title={`${s.label}: ${formatCurrency(s.total)}`}
          />
        ))}
        <div
          className={styles.nwBarSegment}
          style={{ width: `${pct(totalLiabilities)}%`, background: "#f3f3f3", border: "1px solid #da291c", zIndex: 1 }}
          title={`Liabilities: −${formatCurrency(totalLiabilities)}`}
        />
      </div>
      <div className={styles.nwBarLegend}>
        {assetSections.map((s) => (
          <span key={s.key} className={styles.nwBarLegendItem}>
            <span className={styles.legendDot} style={{ background: s.color }} />
            {s.label}
          </span>
        ))}
        <span className={styles.nwBarLegendItem}>
          <span className={styles.legendDot} style={{ background: "#f3f3f3", border: "1px solid #da291c" }} />
          Liabilities
        </span>
      </div>

      {/* ── Asset sections ── */}
      <div className={styles.nwSections}>
        {assetSections.map((section) => (
          <div key={section.key} className={styles.nwSection}>
            <button
              className={styles.nwSectionHeader}
              onClick={() => setExpandedSection(expandedSection === section.key ? null : section.key)}
            >
              <span className={styles.nwSectionIcon}>{section.icon}</span>
              <span className={styles.nwSectionLabel}>{section.label}</span>
              <span className={styles.nwSectionTotal} style={{ color: section.color }}>
                {formatCurrency(section.total)}
              </span>
              <span className={styles.nwSectionPct}>({pct(section.total)}%)</span>
              <span className={`${styles.nwChevron} ${expandedSection === section.key ? styles.nwChevronOpen : ""}`}>
                <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
                  <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </span>
            </button>
            {expandedSection === section.key && (
              <div className={styles.nwSectionBody}>
                {section.items.map((item) => (
                  <div key={item.label} className={styles.nwLineItem}>
                    <span className={styles.nwLineLabel}>
                      {item.label}
                      {(item as { note?: string }).note && <span className={styles.nwLineNote}> · {(item as { note?: string }).note}</span>}
                    </span>
                    <span className={styles.nwLineValue}>{formatCurrency(item.value)}</span>
                  </div>
                ))}
                <button
                  className={styles.nwAskLink}
                  onClick={() => onAskQuestion(`${section.label}: ${formatCurrency(section.total)}`, section.question)}
                >
                  <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
                    <path d="M2 8h12M10 4l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  Ask about this category
                </button>
              </div>
            )}
          </div>
        ))}

        {/* Liabilities section */}
        <div className={styles.nwSection}>
          <button
            className={styles.nwSectionHeader}
            onClick={() => setExpandedSection(expandedSection === "liabilities" ? null : "liabilities")}
          >
            <span className={styles.nwSectionIcon}>🏦</span>
            <span className={styles.nwSectionLabel}>Liabilities</span>
            <span className={styles.nwSectionTotal} style={{ color: "#da291c" }}>−{formatCurrency(totalLiabilities)}</span>
            <span className={styles.nwSectionPct}>({pct(totalLiabilities)}% of assets)</span>
            <span className={`${styles.nwChevron} ${expandedSection === "liabilities" ? styles.nwChevronOpen : ""}`}>
              <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
                <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
          </button>
            {expandedSection === "liabilities" && (
            <div className={styles.nwSectionBody}>
              {data.liabilities.map((l: any) => (
                <div key={l.label} className={styles.nwLineItem}>
                  <span className={styles.nwLineLabel}>
                    {l.label}
                    {l.rate && <span className={styles.nwLineNote}> · {l.rate} p.a.</span>}
                    {"note" in l && l.note && <span className={styles.nwLineNote}> · {l.note}</span>}
                  </span>
                  <span className={styles.nwLineValue} style={{ color: "#da291c" }}>−{formatCurrency(Math.abs(l.value))}</span>
                </div>
              ))}
              <button
                className={styles.nwAskLink}
                onClick={() => onAskQuestion(
                  `Total liabilities: ${formatCurrency(totalLiabilities)}`,
                  `My total liabilities are ${formatCurrency(totalLiabilities)}, including a Lombard loan and mortgage. What is your assessment of my leverage ratio and debt servicing capacity?`,
                )}
              >
                <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
                  <path d="M2 8h12M10 4l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                Ask about liabilities
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Summary Cards ───────────────────────────────────────────────────────────

function SummaryCards({ currentValue, asOf, customerId, customerName, returnMetrics, riskMetrics }: {
  currentValue: number,
  asOf: string,
  customerId: string,
  customerName: string,
  returnMetrics: { six_month_return_pct: number; ytd_return_pct: number; one_year_return_pct: number },
  riskMetrics: { risk_profile: string; sharpe_ratio: number; volatility_pct: number }
}) {
  const sixMonthReturn = returnMetrics.six_month_return_pct;
  const ytdReturn = returnMetrics.ytd_return_pct;
  const oneYearReturn = returnMetrics.one_year_return_pct;

  const cards = [
    { label: "Portfolio Value", value: formatCurrency(currentValue), sub: `As of ${asOf} · ${customerName} (${customerId})` },
    { label: "6M Return", value: `${sixMonthReturn >= 0 ? "+" : ""}${sixMonthReturn.toFixed(1)}%`, sub: "Compounded monthly returns" },
    { label: "YTD Return", value: `${ytdReturn >= 0 ? "+" : ""}${ytdReturn.toFixed(1)}%`, sub: "From portfolio summary" },
    { label: "1Y Return", value: `${oneYearReturn >= 0 ? "+" : ""}${oneYearReturn.toFixed(1)}%`, sub: `Risk: ${riskMetrics.risk_profile} · Sharpe: ${riskMetrics.sharpe_ratio.toFixed(2)}` },
  ];

  return (
    <div className={styles.summaryGrid}>
      {cards.map((card) => (
        <div key={card.label} className={styles.summaryCard}>
          <span className={styles.summaryLabel}>{card.label}</span>
          <span className={styles.summaryValue}>{card.value}</span>
          <span className={styles.summarySub}>{card.sub}</span>
        </div>
      ))}
    </div>
  );
}

// ─── Portfolio Value Line Chart ──────────────────────────────────────────────

function PortfolioChart({ 
  data, 
  onClickPoint 
}: { 
  data: { month: string; value: number }[],
  onClickPoint: (context: string, suggestion: string) => void 
}) {
  const [hovered, setHovered] = useState<number | null>(null);
  
  if (!data || data.length === 0) {
    return (
      <div className={styles.chartCard}>
        <h3 className={styles.chartTitle}>Portfolio Value Over Time</h3>
        <p className={styles.chartSubtitle}>No data available for this period</p>
      </div>
    );
  }

  const values = data.map((d) => d.value);
  const maxVal = Math.max(...values);
  const minVal = Math.min(...values);
  const range = maxVal - minVal || 1;
  const W = 500;
  const H = 200;
  const padLeft = 60;
  const padRight = 20;
  const padTop = 20;
  const padBottom = 36;
  const innerW = W - padLeft - padRight;
  const innerH = H - padTop - padBottom;

  const points = values.map((v, i) => ({
    x: padLeft + (i / (values.length - 1)) * innerW,
    y: padTop + innerH - ((v - minVal) / range) * innerH,
    v,
  }));
  const polyline = points.map((p) => `${p.x},${p.y}`).join(" ");

  return (
    <div className={styles.chartCard}>
      <h3 className={styles.chartTitle}>Portfolio Value Over Time</h3>
      <p className={styles.chartSubtitle}>Click on any data point to ask about that period</p>
      <svg viewBox={`0 0 ${W} ${H}`} className={styles.chartSvg}>
        {[0, 0.25, 0.5, 0.75, 1].map((frac) => {
          const y = padTop + innerH * (1 - frac);
          const val = minVal + range * frac;
          return (
            <g key={frac}>
              <line x1={padLeft} y1={y} x2={W - padRight} y2={y} stroke="var(--color-border)" strokeWidth={0.5} strokeDasharray="3 3" />
              <text x={padLeft - 8} y={y + 3} textAnchor="end" className={styles.axisLabel}>
                {(val / 1000).toFixed(0)}K
              </text>
            </g>
          );
        })}
        <polygon
          points={`${padLeft},${padTop + innerH} ${polyline} ${points[points.length - 1]!.x},${padTop + innerH}`}
          fill="#da291c" fillOpacity={0.08}
        />
        <polyline points={polyline} fill="none" stroke="#da291c" strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" />
        {points.map((p, i) => {
          const d = data[i]!;
          return (
            <g key={i}>
              <circle
                cx={p.x} cy={p.y} r={hovered === i ? 7 : 4.5}
                fill="#da291c" stroke="var(--color-bg)" strokeWidth={2}
                className={styles.clickableDot}
                onMouseEnter={() => setHovered(i)}
                onMouseLeave={() => setHovered(null)}
                onClick={() => onClickPoint(
                  `Portfolio value in ${d.month}: ${formatCurrency(d.value)}`,
                  `Why did my portfolio value ${data[0] && d.value > data[0].value ? "increase" : "decrease"} to ${formatCurrency(d.value)} in ${d.month}? What were the key drivers?`,
                )}
              />
              {hovered === i && (
                <text x={p.x} y={p.y - 14} textAnchor="middle" className={styles.tooltipLabel}>
                  {formatCurrency(p.v)}
                </text>
              )}
              <text x={p.x} y={H - padBottom + 16} textAnchor="middle" className={styles.axisLabel}>
                {d.month}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ─── Asset Allocation Pie Chart ──────────────────────────────────────────────

function AllocationChart({ 
  data, 
  onClickSlice 
}: { 
  data: { label: string; value: number; color?: string }[],
  onClickSlice: (context: string, suggestion: string) => void 
}) {
  const [hovered, setHovered] = useState<number | null>(null);
  const total = data.reduce((s: number, d: any) => s + d.value, 0);
  const cx = 100;
  const cy = 100;
  const r = 85;

  let cumulative = 0;
  const slices = data.map((d: any, i: number) => {
    const startAngle = (cumulative / total) * 360;
    cumulative += d.value;
    const endAngle = (cumulative / total) * 360;
    return { ...d, startAngle, endAngle, i, color: d.color || ALLOCATION_COLORS[i % ALLOCATION_COLORS.length] };
  });

  return (
    <div className={styles.chartCard}>
      <h3 className={styles.chartTitle}>Asset Allocation</h3>
      <p className={styles.chartSubtitle}>Click on a segment to ask about that asset class</p>
      <div className={styles.pieLayout}>
        <svg viewBox="0 0 200 200" className={styles.pieSvg}>
          {slices.map((s) => (
            <path
              key={s.i}
              d={pieSlicePath(cx, cy, r, s.startAngle, s.endAngle)}
              fill={s.color}
              stroke="var(--color-bg)" strokeWidth={2}
              opacity={hovered !== null && hovered !== s.i ? 0.5 : 1}
              className={styles.clickableSlice}
              onMouseEnter={() => setHovered(s.i)}
              onMouseLeave={() => setHovered(null)}
              onClick={() => onClickSlice(
                `${s.label}: ${s.value}% of portfolio`,
                `Can you explain my ${s.label} allocation of ${s.value}%? Is this appropriate for my risk profile and should I consider rebalancing?`,
              )}
            />
          ))}
          <circle cx={cx} cy={cy} r={42} fill="var(--color-bg)" />
          <text x={cx} y={cy - 4} textAnchor="middle" className={styles.donutLabel}>{total}%</text>
          <text x={cx} y={cy + 12} textAnchor="middle" className={styles.donutSub}>Allocated</text>
        </svg>
        <div className={styles.pieLegend}>
          {slices.map((d, i) => (
            <div
              key={d.label}
              className={`${styles.legendItem} ${hovered === i ? styles.legendActive : ""}`}
              onMouseEnter={() => setHovered(i)}
              onMouseLeave={() => setHovered(null)}
              onClick={() => onClickSlice(
                `${d.label}: ${d.value}% of portfolio`,
                `Can you explain my ${d.label} allocation of ${d.value}%? Is this appropriate for my risk profile and should I consider rebalancing?`,
              )}
            >
              <span className={styles.legendDot} style={{ background: d.color }} />
              <span className={styles.legendLabel}>{d.label}</span>
              <span className={styles.legendValue}>{d.value}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Monthly Returns Bar Chart ───────────────────────────────────────────────

function ReturnsChart({ 
  data, 
  onClickBar 
}: { 
  data: { month: string; value: number }[],
  onClickBar: (context: string, suggestion: string) => void 
}) {
  const [hovered, setHovered] = useState<number | null>(null);
  const maxVal = Math.max(...data.map((d: any) => Math.abs(d.value)));
  const W = 500;
  const H = 200;
  const padLeft = 40;
  const padRight = 20;
  const padTop = 20;
  const padBottom = 36;
  const innerW = W - padLeft - padRight;
  const innerH = H - padTop - padBottom;
  const zeroY = padTop + innerH / 2;
  const barW = innerW / data.length - 16;
  const gap = innerW / data.length;

  return (
    <div className={styles.chartCard}>
      <h3 className={styles.chartTitle}>Monthly Returns (%)</h3>
      <p className={styles.chartSubtitle}>Click a bar to ask about that month's performance</p>
      <svg viewBox={`0 0 ${W} ${H}`} className={styles.chartSvg}>
        <line x1={padLeft} y1={zeroY} x2={W - padRight} y2={zeroY} stroke="var(--color-border)" strokeWidth={1} />
        {[-maxVal, 0, maxVal].map((val) => {
          const y = zeroY - (val / maxVal) * (innerH / 2);
          return (
            <text key={val} x={padLeft - 6} y={y + 3} textAnchor="end" className={styles.axisLabel}>
              {val > 0 ? `+${val.toFixed(0)}` : val.toFixed(0)}%
            </text>
          );
        })}
        {data.map((d: any, i: number) => {
          const barH = (Math.abs(d.value) / maxVal) * (innerH / 2);
          const x = padLeft + gap * i + (gap - barW) / 2;
          const y = d.value >= 0 ? zeroY - barH : zeroY;
          const color = d.value >= 0 ? "#1e1e1e" : "#da291c";
          return (
            <g key={i}>
              <rect
                x={x} y={y} width={barW} height={barH}
                fill={color} opacity={hovered !== null && hovered !== i ? 0.4 : 0.85}
                rx={3} className={styles.clickableBar}
                onMouseEnter={() => setHovered(i)}
                onMouseLeave={() => setHovered(null)}
                onClick={() => onClickBar(
                  `${d.month} return: ${d.value > 0 ? "+" : ""}${d.value}%`,
                  `My portfolio returned ${d.value > 0 ? "+" : ""}${d.value}% in ${d.month}. What factors contributed to this ${d.value >= 0 ? "gain" : "loss"}?`,
                )}
              />
              {hovered === i && (
                <text x={x + barW / 2} y={d.value >= 0 ? y - 6 : y + barH + 14} textAnchor="middle" className={styles.tooltipLabel}>
                  {d.value > 0 ? "+" : ""}{d.value}%
                </text>
              )}
              <text x={x + barW / 2} y={H - padBottom + 16} textAnchor="middle" className={styles.axisLabel}>
                {d.month}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ─── Insights & Opportunities ────────────────────────────────────────────────

interface RmNotifyPanelProps {
  signal: InsightSignal;
  relationshipManager: PerformanceData["relationship_manager"];
  onClose: () => void;
}

function RmNotifyPanel({ signal, relationshipManager, onClose }: RmNotifyPanelProps) {
  const [sent, setSent] = useState(false);
  const [message, setMessage] = useState(
    `Dear ${relationshipManager.name},\n\n${signal.rm_context}\n\nPlease could we discuss this at your earliest convenience?\n\nKind regards,\nClient`,
  );

  function handleSend() {
    setSent(true);
  }

  return (
    <div className={styles.rmPanel}>
      <div className={styles.rmPanelHeader}>
        <div className={styles.rmPanelTitle}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M13 2H3a1 1 0 00-1 1v8a1 1 0 001 1h2l3 2 3-2h2a1 1 0 001-1V3a1 1 0 00-1-1z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
          </svg>
          Notify Relationship Manager
        </div>
        <div className={styles.rmPanelMeta}>{relationshipManager.name} · {relationshipManager.email} · {relationshipManager.phone}</div>
        <button className={styles.rmPanelClose} onClick={onClose} aria-label="Close">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
            <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>
      </div>
      {sent ? (
        <div className={styles.rmSentState}>
          <span className={styles.rmSentIcon}>✓</span>
          <div>
            <p className={styles.rmSentTitle}>Message sent to {relationshipManager.name}</p>
            <p className={styles.rmSentSub}>Your relationship manager will be in touch shortly. This is a notification only — no actions have been executed on your account.</p>
          </div>
        </div>
      ) : (
        <>
          <div className={styles.rmDisclaimer}>
            <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5" />
              <path d="M8 5v3M8 10.5v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            This is a suggestion only. No actions will be executed. Your RM will follow up to discuss options at your discretion.
          </div>
          <textarea
            className={styles.rmTextarea}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={7}
          />
          <div className={styles.rmPanelActions}>
            <button className={styles.rmCancelBtn} onClick={onClose}>Cancel</button>
            <button className={styles.rmSendBtn} onClick={handleSend} disabled={!message.trim()}>
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <path d="M2 8h12M10 4l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Send to {relationshipManager.name}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

interface InsightSignal {
  id: string;
  priority: "high" | "medium" | "low";
  category: string;
  icon: string;
  title: string;
  trigger: string;
  summary: string;
  suggested_actions: string[];
  rm_context: string;
  tags: string[];
}

function InsightCard({ signal, relationshipManager }: { signal: InsightSignal; relationshipManager: PerformanceData["relationship_manager"] }) {
  const [expanded, setExpanded] = useState(false);
  const [showRmPanel, setShowRmPanel] = useState(false);

  const priorityClass = signal.priority === "high" ? styles.priorityHigh : signal.priority === "medium" ? styles.priorityMedium : styles.priorityLow;
  const priorityLabel = signal.priority === "high" ? "Priority" : signal.priority === "medium" ? "Consider" : "FYI";

  return (
    <div className={`${styles.insightCard} ${signal.priority === "high" ? styles.insightCardHigh : ""}`}>
      <div className={styles.insightCardTop}>
        <div className={styles.insightIconWrap}>
          <span className={styles.insightIcon}>{signal.icon}</span>
        </div>
        <div className={styles.insightCardMain}>
          <div className={styles.insightCardMeta}>
            <span className={`${styles.priorityBadge} ${priorityClass}`}>{priorityLabel}</span>
            <span className={styles.insightCategory}>{signal.category}</span>
          </div>
          <h4 className={styles.insightTitle}>{signal.title}</h4>
          <p className={styles.insightTrigger}>
            <svg width="11" height="11" viewBox="0 0 16 16" fill="none" style={{ flexShrink: 0 }}>
              <circle cx="8" cy="8" r="3" fill="currentColor" />
              <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.5" />
            </svg>
            {signal.trigger}
          </p>
          <p className={styles.insightSummary}>{signal.summary}</p>
          <div className={styles.insightTags}>
            {(signal.tags ?? []).map((tag: any) => (
              <span key={tag} className={styles.insightTag}>{tag}</span>
            ))}
          </div>
        </div>
      </div>

      <button
        className={styles.insightExpandBtn}
        onClick={() => setExpanded(!expanded)}
      >
        <span>{expanded ? "Hide" : "View"} suggested actions</span>
        <span className={`${styles.insightChevron} ${expanded ? styles.insightChevronOpen : ""}`}>
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
            <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
      </button>

      {expanded && (
        <div className={styles.insightActions}>
          <ol className={styles.insightActionList}>
            {(signal.suggested_actions ?? []).map((action: any, i: number) => (
              <li key={i} className={styles.insightActionItem}>
                <span className={styles.insightActionNum}>{i + 1}</span>
                <span>{action}</span>
              </li>
            ))}
          </ol>
          <div className={styles.insightActionsFooter}>
            <p className={styles.insightDisclaimer}>
              These are suggestions only. No actions will be executed without your explicit instruction.
            </p>
            <button
              className={styles.notifyRmBtn}
              onClick={() => setShowRmPanel(true)}
            >
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <path d="M13 2H3a1 1 0 00-1 1v8a1 1 0 001 1h2l3 2 3-2h2a1 1 0 001-1V3a1 1 0 00-1-1z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
              </svg>
              Notify RM to Follow Up
            </button>
          </div>
          {showRmPanel && (
            <RmNotifyPanel signal={signal} relationshipManager={relationshipManager} onClose={() => setShowRmPanel(false)} />
          )}
        </div>
      )}
    </div>
  );
}

function InsightsOpportunities({ insights, relationshipManager }: { insights: InsightSignal[]; relationshipManager: PerformanceData["relationship_manager"] }) {
  const [filter, setFilter] = useState<"all" | "high" | "medium">("all");

  const filtered = filter === "all"
    ? insights
    : insights.filter((s) => s.priority === filter);

  const highCount = insights.filter((s) => s.priority === "high").length;
  const mediumCount = insights.filter((s) => s.priority === "medium").length;

  return (
    <div className={styles.insightsSection}>
      <div className={styles.insightsHeader}>
        <div>
          <h2 className={styles.insightsTitle}>
            <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
              <circle cx="10" cy="10" r="9" stroke="currentColor" strokeWidth="1.5" />
              <path d="M10 6v5M10 13.5v.5" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
            </svg>
            Insights & Opportunities
          </h2>
          <p className={styles.insightsSubtitle}>
            Based on your recent activity, transactions, and financial profile — curated suggestions for your consideration.
          </p>
        </div>
        <div className={styles.insightsBadgeRow}>
          <span className={styles.insightsSummaryBadge} style={{ background: "#fef2f2", color: "#b91c1c", border: "1px solid #fecaca" }}>
            {highCount} Priority
          </span>
          <span className={styles.insightsSummaryBadge} style={{ background: "#fffbeb", color: "#92400e", border: "1px solid #fde68a" }}>
            {mediumCount} Consider
          </span>
        </div>
      </div>

      <div className={styles.insightsFilters}>
        {(["all", "high", "medium"] as const).map((f) => (
          <button
            key={f}
            className={`${styles.insightsFilterBtn} ${filter === f ? styles.insightsFilterActive : ""}`}
            onClick={() => setFilter(f)}
          >
            {f === "all" ? `All (${insights.length})` : f === "high" ? `Priority (${highCount})` : `Consider (${mediumCount})`}
          </button>
        ))}
      </div>

      <div className={styles.insightsList}>
        {filtered.map((signal) => (
          <InsightCard key={signal.id} signal={signal} relationshipManager={relationshipManager} />
        ))}
      </div>

      <p className={styles.insightsDisclaimer}>
        ⚠ All insights are generated from your activity data for informational purposes only. No actions are executed by the system. Please contact your Relationship Manager to discuss any of the above.
      </p>
    </div>
  );
}

// ─── Benchmark Comparison ────────────────────────────────────────────────────

function BenchmarkChart({ 
  data, 
  benchmarkName,
  onClickPoint 
}: { 
  data: { month: string; portfolio: number; benchmark: number }[],
  benchmarkName: string,
  onClickPoint: (context: string, suggestion: string) => void 
}) {
  const [hovered, setHovered] = useState<number | null>(null);
  const safeData = (Array.isArray(data) ? data : []).filter(
    (entry) => Number.isFinite(entry?.portfolio) && Number.isFinite(entry?.benchmark),
  );

  if (safeData.length < 2) {
    return (
      <div className={styles.chartCard}>
        <h3 className={styles.chartTitle}>Portfolio vs Benchmark</h3>
        <p className={styles.chartSubtitle}>Not enough benchmark data available yet.</p>
      </div>
    );
  }

  const allValues = safeData.flatMap((d: any) => [d.portfolio, d.benchmark]);
  const maxVal = Math.max(...allValues);
  const minVal = Math.min(...allValues);
  const range = maxVal - minVal || 1;
  const W = 500;
  const H = 200;
  const padLeft = 40;
  const padRight = 20;
  const padTop = 20;
  const padBottom = 36;
  const innerW = W - padLeft - padRight;
  const innerH = H - padTop - padBottom;

  function getPoints(key: "portfolio" | "benchmark") {
    return safeData.map((d: any, i: number) => ({
      x: padLeft + (i / (safeData.length - 1)) * innerW,
      y: padTop + innerH - ((d[key] - minVal) / range) * innerH,
      v: d[key],
    }));
  }

  const portfolioPoints = getPoints("portfolio");
  const benchmarkPoints = getPoints("benchmark");

  return (
    <div className={styles.chartCard}>
      <h3 className={styles.chartTitle}>Portfolio vs Benchmark</h3>
      <p className={styles.chartSubtitle}>Click a point to compare your performance against the benchmark</p>
      <div className={styles.benchmarkLegend}>
        <span className={styles.benchmarkKey}><span className={styles.legendDot} style={{ background: "#da291c" }} /> Your Portfolio</span>
        <span className={styles.benchmarkKey}><span className={styles.legendDot} style={{ background: "#1e1e1e" }} /> Benchmark ({benchmarkName})</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className={styles.chartSvg}>
        {[0, 0.5, 1].map((frac) => {
          const y = padTop + innerH * (1 - frac);
          const val = minVal + range * frac;
          return (
            <g key={frac}>
              <line x1={padLeft} y1={y} x2={W - padRight} y2={y} stroke="var(--color-border)" strokeWidth={0.5} strokeDasharray="3 3" />
              <text x={padLeft - 6} y={y + 3} textAnchor="end" className={styles.axisLabel}>
                {val > 0 ? "+" : ""}{val.toFixed(1)}%
              </text>
            </g>
          );
        })}
        <polyline
          points={benchmarkPoints.map((p) => `${p.x},${p.y}`).join(" ")}
          fill="none" stroke="#1e1e1e" strokeWidth={2} strokeLinejoin="round" strokeDasharray="6 3"
        />
        <polyline
          points={portfolioPoints.map((p) => `${p.x},${p.y}`).join(" ")}
          fill="none" stroke="#da291c" strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round"
        />
        {portfolioPoints.map((p, i: number) => {
          const d = safeData[i]!;
          const diff = d.portfolio - d.benchmark;
          return (
            <g key={i}>
              <circle
                cx={p.x} cy={p.y} r={hovered === i ? 7 : 4.5}
                fill="#da291c" stroke="var(--color-bg)" strokeWidth={2}
                className={styles.clickableDot}
                onMouseEnter={() => setHovered(i)}
                onMouseLeave={() => setHovered(null)}
                onClick={() => onClickPoint(
                  `${d.month}: Portfolio ${d.portfolio > 0 ? "+" : ""}${d.portfolio}% vs Benchmark ${d.benchmark > 0 ? "+" : ""}${d.benchmark}%`,
                  `In ${d.month}, my portfolio returned ${d.portfolio > 0 ? "+" : ""}${d.portfolio}% vs the benchmark at ${d.benchmark > 0 ? "+" : ""}${d.benchmark}%. Why did I ${diff >= 0 ? "outperform" : "underperform"} by ${Math.abs(diff).toFixed(1)}%?`,
                )}
              />
              {hovered === i && (
                <text x={p.x} y={p.y - 14} textAnchor="middle" className={styles.tooltipLabel}>
                  Portfolio: {p.v > 0 ? "+" : ""}{p.v}%
                </text>
              )}
              <text x={p.x} y={H - padBottom + 16} textAnchor="middle" className={styles.axisLabel}>
                {d.month}
              </text>
            </g>
          );
        })}
        {benchmarkPoints.map((p, i: number) => (
          <circle key={`b${i}`} cx={p.x} cy={p.y} r={3} fill="#1e1e1e" stroke="var(--color-bg)" strokeWidth={1.5} />
        ))}
      </svg>
    </div>
  );
}

// ─── Main Page ───────────────────────────────────────────────────────────────

export function PerformancePage({ onAskQuestion, onBack }: PerformancePageProps) {
  const [data, setData] = useState<PerformanceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeQuestion, setActiveQuestion] = useState<{ context: string; suggestion: string } | null>(null);

  useEffect(() => {
    async function fetchPerformance() {
      try {
        const token = localStorage.getItem("access_token");
        if (!token) {
          throw new Error("Missing auth token. Please sign in again.");
        }
        const response = await fetch("http://localhost:8000/api/customers/me/performance", {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        if (!response.ok) throw new Error("Failed to fetch performance data");
        const json = await response.json();
        setData(normalizePerformanceData(json));
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    fetchPerformance();
  }, []);

  const handleDataPointClick = useCallback((context: string, suggestion: string) => {
    setActiveQuestion({ context, suggestion });
  }, []);

  function handleSendQuestion(question: string) {
    setActiveQuestion(null);
    onAskQuestion(question);
  }

  if (loading) {
    return (
      <div className={styles.page}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: '1rem' }}>
          <div className={styles.spinner} />
          <p>Analyzing portfolio performance...</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className={styles.page}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: '1rem' }}>
          <p style={{ color: '#da291c' }}>Error: {error || "Unable to load performance data"}</p>
          <button onClick={() => window.location.reload()} style={{ padding: '0.5rem 1rem', background: '#da291c', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>Retry</button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <button className={styles.backButton} onClick={onBack}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M10 12L6 8L10 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Back to Chat
        </button>
        <h1 className={styles.pageTitle}>Account Performance</h1>
        <p className={styles.pageSubtitle}>Click on any chart data point to ask your advisor about it</p>
      </header>

      <div className={styles.content}>
        <SummaryCards 
          currentValue={data.portfolio_current_value}
          asOf={data.net_worth.asOf}
          customerId={data.net_worth.customerId} 
          customerName={data.net_worth.customer} 
          returnMetrics={data.return_metrics}
          riskMetrics={data.risk_metrics}
        />

        {activeQuestion && (
          <QuestionPanel
            context={activeQuestion.context}
            suggestedQuestion={activeQuestion.suggestion}
            onSend={handleSendQuestion}
            onDismiss={() => setActiveQuestion(null)}
          />
        )}

        <NetWorthCalculator data={data.net_worth} onAskQuestion={handleDataPointClick} />

        <div className={styles.chartsGrid}>
          <PortfolioChart data={data.portfolio_value} onClickPoint={handleDataPointClick} />
          <AllocationChart data={data.asset_allocation} onClickSlice={handleDataPointClick} />
          <ReturnsChart data={data.monthly_returns} onClickBar={handleDataPointClick} />
          <BenchmarkChart data={data.benchmark_comparison} benchmarkName={data.benchmark_name} onClickPoint={handleDataPointClick} />
        </div>

        <InsightsOpportunities insights={data.insights} relationshipManager={data.relationship_manager} />
      </div>
    </div>
  );
}

