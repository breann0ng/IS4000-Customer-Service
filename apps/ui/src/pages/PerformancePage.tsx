import { useRef, useState, useEffect } from "react";
import styles from "./PerformancePage.module.css";

interface PerformancePageProps {
  onAskQuestion: (question: string) => void;
  onBack: () => void;
}

// ─── Insights & Opportunities Mock Data ─────────────────────────────────────

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

const INSIGHTS_SIGNALS: InsightSignal[] = [
  {
    id: "INS-001",
    priority: "high",
    category: "Lifestyle & Protection",
    icon: "🚗",
    title: "New Vehicle Requires Insurance & COE Review",
    trigger: "Rolls-Royce Ghost Black Badge purchase — SGD 1.45M (Incl. COE) on 24 Mar 2026",
    summary: "Your recent luxury vehicle acquisition includes significant ARF and COE exposure. A bespoke private client motor insurance arrangement is recommended.",
    suggested_actions: [
      "Arrange agreed-value motor insurance for the Rolls-Royce Ghost",
      "Review PARF/COE rebate status for existing vehicles",
    ],
    rm_context: "Client acquired a Rolls-Royce Ghost (SGD 1.45M, 24 Mar 2026). Recommend motor insurance review.",
    tags: ["Insurance", "COE", "Vehicle"],
  },
  {
    id: "INS-002",
    priority: "medium",
    category: "Lifestyle & Memberships",
    icon: "⛳",
    title: "Exclusive Concierge Services for Sentosa Membership",
    trigger: "Sentosa Golf Club membership joins — SGD 650k on 18 Mar 2026",
    summary: "As a member of one of the world's premier clubs, you now have access to UBS's global lifestyle partnerships.",
    suggested_actions: [
      "Connect with UBS Lifestyle Services for private culinary experiences",
      "Explore curated regional golf travel",
    ],
    rm_context: "Client joined Sentosa Golf Club (SGD 650k, 18 Mar 2026).",
    tags: ["Lifestyle", "Concierge"],
  },
];

// ─── Helpers ─────────────────────────────────────────────────────────────────

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

  useEffect(() => {
    setQuestion(suggestedQuestion);
  }, [suggestedQuestion]);

  function handleSend() {
    const trimmed = question.trim();
    if (trimmed) onSend(trimmed);
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
        <button className={styles.questionSendButton} onClick={handleSend} disabled={!question.trim()}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M2 8h12M10 4l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Ask
        </button>
      </div>
    </div>
  );
}

// ─── Sub-Components ──────────────────────────────────────────────────────────

function SummaryCards({ portfolioValue, profile }: { portfolioValue: any[], profile: any }) {
  if (!portfolioValue.length) return null;
  const currentValue = portfolioValue[portfolioValue.length - 1].value;
  const previousValue = portfolioValue[0].value;
  const totalReturn = (((currentValue - previousValue) / previousValue) * 100).toFixed(1);
  const ytdReturn = profile.ytd_return_pct ? profile.ytd_return_pct.toFixed(1) : "0.0";

  const cards = [
    { label: "Portfolio Value", value: formatCurrency(currentValue), sub: `As of Mar 2026 · ${profile.full_name}` },
    { label: "Return (Period)", value: `+${totalReturn}%`, sub: `+${formatCurrency(currentValue - previousValue)}` },
    { label: "YTD Return", value: `+${ytdReturn}%`, sub: "Jan - Mar 2026" },
    { label: "Risk Level", value: profile.risk_profile, sub: "Sharpe Ratio: 1.55" },
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

function NetWorthCalculator({ data, profile }: { data: any, profile: any }) {
  
  const totalLiquid = (data.liquidAssets || []).reduce((s: any, a: any) => s + a.value, 0);
  const totalPortfolio = (data.investmentPortfolio || []).reduce((s: any, a: any) => s + a.value, 0);
  const totalAssets = totalLiquid + totalPortfolio;
  const netWorth = totalAssets; // Simplified for now

  const pct = (val: number) => Math.round((val / totalAssets) * 100) || 0;

  const sections = [
    { key: "liquid", label: "Liquid & Cash Assets", total: totalLiquid, items: data.liquidAssets, color: "#da291c", icon: "💵" },
    { key: "portfolio", label: "Investment Portfolio", total: totalPortfolio, items: data.investmentPortfolio, color: "#1e1e1e", icon: "📈" },
  ];

  return (
    <div className={styles.netWorthCard}>
      <div className={styles.netWorthHeader}>
        <div>
          <h3 className={styles.netWorthTitle}>Net Worth Snapshot</h3>
          <p className={styles.netWorthSubtitle}>Client: {profile.full_name} · All values in SGD</p>
        </div>
      </div>
      <div className={styles.nwKpis}>
        <div className={styles.nwKpi}>
          <span className={styles.nwKpiLabel}>Total Assets</span>
          <span className={styles.nwKpiValue}>{formatCurrency(totalAssets)}</span>
        </div>
        <div className={styles.nwKpiDivider} />
        <div className={styles.nwKpi}>
          <span className={styles.nwKpiLabel}>Net Worth</span>
          <span className={styles.nwKpiValue} style={{ color: "#16a34a" }}>{formatCurrency(netWorth)}</span>
        </div>
      </div>
      <div className={styles.nwBar}>
        {sections.map(s => (
          <div key={s.key} className={styles.nwBarSegment} style={{ width: `${pct(s.total)}%`, background: s.color }} />
        ))}
      </div>
    </div>
  );
}

function PortfolioChart({ data, onClickPoint }: { data: any[], onClickPoint: any }) {
  const [hovered, setHovered] = useState<number | null>(null);
  if (!data.length) return null;
  const values = data.map(d => d.value);
  const maxVal = Math.max(...values);
  const minVal = Math.min(...values);
  const range = maxVal - minVal || 1;
  const W = 500, H = 200, padLeft = 60, padRight = 20, padTop = 20, padBottom = 36;
  const innerW = W - padLeft - padRight, innerH = H - padTop - padBottom;

  const points = values.map((v, i) => ({
    x: padLeft + (i / (values.length - 1)) * innerW,
    y: padTop + innerH - ((v - minVal) / range) * innerH,
    v
  }));
  const polyline = points.map(p => `${p.x},${p.y}`).join(" ");

  return (
    <div className={styles.chartCard}>
      <h3 className={styles.chartTitle}>Portfolio Value Over Time</h3>
      <svg viewBox={`0 0 ${W} ${H}`} className={styles.chartSvg}>
        <polyline points={polyline} fill="none" stroke="#da291c" strokeWidth={2.5} />
        {points.map((p, i) => (
          <circle 
            key={i} cx={p.x} cy={p.y} r={hovered === i ? 7 : 4} fill="#da291c" 
            onMouseEnter={() => setHovered(i)} onMouseLeave={() => setHovered(null)}
            onClick={() => onClickPoint(`Value in ${data[i].month}: ${formatCurrency(p.v)}`, `What drove the performance in ${data[i].month}?`)}
          />
        ))}
      </svg>
    </div>
  );
}

function AllocationChart({ data, onClickSlice }: { data: any[], onClickSlice: any }) {
  return (
    <div className={styles.chartCard}>
      <h3 className={styles.chartTitle}>Asset Allocation</h3>
      <div className={styles.pieLegend}>
        {data.map(d => (
          <div key={d.label} className={styles.legendItem} onClick={() => onClickSlice(`${d.label}: ${d.value}%`, `Tell me more about my ${d.label} allocation.`)}>
            <span className={styles.legendDot} style={{ background: d.color }} />
            <span>{d.label}</span>
            <span>{d.value}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ReturnsChart({ data, onClickBar }: { data: any[], onClickBar: any }) {
  return (
    <div className={styles.chartCard}>
      <h3 className={styles.chartTitle}>Monthly Returns (%)</h3>
      <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-end', height: '100px', padding: '20px' }}>
        {data.map((d, i) => (
          <div 
            key={i} 
            style={{ flex: 1, background: d.value >= 0 ? '#1e1e1e' : '#da291c', height: `${Math.abs(d.value) * 10}px` }} 
            onClick={() => onClickBar(`${d.month}: ${d.value}%`, `Why did I get a ${d.value}% return in ${d.month}?`)}
          />
        ))}
      </div>
    </div>
  );
}

function InsightsOpportunities() {
  return (
    <div className={styles.insightsSection}>
      <h2 className={styles.insightsTitle}>Insights & Opportunities</h2>
      <div className={styles.insightsList}>
        {INSIGHTS_SIGNALS.map(s => (
          <div key={s.id} className={styles.insightCard}>
            <h4>{s.icon} {s.title}</h4>
            <p>{s.summary}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Main Export ─────────────────────────────────────────────────────────────

export function PerformancePage({ onAskQuestion, onBack }: PerformancePageProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [activeQuestion, setActiveQuestion] = useState<{ context: string; suggestion: string } | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const token =
          localStorage.getItem("access_token") || localStorage.getItem("token");
        const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
        const [sRes, hRes] = await Promise.all([
          fetch("/api/portfolio/summary", { headers }),
          fetch("/api/portfolio/performance", { headers })
        ]);
        if (sRes.status === 401 || hRes.status === 401) {
          localStorage.removeItem("access_token");
          localStorage.removeItem("token");
          window.location.href = "/login";
          return;
        }
        if (!sRes.ok || !hRes.ok) throw new Error("Failed to fetch data");
        setSummary(await sRes.json());
        setHistory(await hRes.json());
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  if (loading) return <div className={styles.loadingContainer}><p>Loading portfolio...</p></div>;
  if (error || !summary) return <div className={styles.errorContainer}><p>{error || "Error"}</p><button onClick={onBack}>Back</button></div>;

  const { profile, portfolio, accounts } = summary;
  const PORTFOLIO_VALUE = history.map((h: any) => ({ month: h.month, value: h.value_usd }));
  const MONTHLY_RETURNS = history.map((h: any) => ({ month: h.month, value: h.return_pct }));
  const ASSET_ALLOCATION = [
    { label: "Equities", value: portfolio.equities_pct, color: "#da291c" },
    { label: "Fixed Income", value: portfolio.fixed_income_pct, color: "#1e1e1e" },
    { label: "Cash", value: portfolio.cash_pct, color: "#888888" },
  ];
  const NET_WORTH_DATA = {
    liquidAssets: accounts.map((a: any) => ({ label: a.account_type, value: a.balance })),
    investmentPortfolio: ASSET_ALLOCATION.map((aa: any) => ({ label: aa.label, value: (aa.value / 100) * profile.aum_usd }))
  };

  const handleDataPointClick = (context: string, suggestion: string) => setActiveQuestion({ context, suggestion });

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <button className={styles.backButton} onClick={onBack}>Back</button>
        <h1 className={styles.pageTitle}>Account Performance</h1>
      </header>
      <div className={styles.content}>
        <SummaryCards portfolioValue={PORTFOLIO_VALUE} profile={profile} />
        {activeQuestion && (
          <QuestionPanel 
            context={activeQuestion.context} 
            suggestedQuestion={activeQuestion.suggestion} 
            onSend={(q) => { setActiveQuestion(null); onAskQuestion(q); }} 
            onDismiss={() => setActiveQuestion(null)} 
          />
        )}
        <NetWorthCalculator data={NET_WORTH_DATA} profile={profile} />
        <div className={styles.chartsGrid}>
          <PortfolioChart data={PORTFOLIO_VALUE} onClickPoint={handleDataPointClick} />
          <AllocationChart data={ASSET_ALLOCATION} onClickSlice={handleDataPointClick} />
          <ReturnsChart data={MONTHLY_RETURNS} onClickBar={handleDataPointClick} />
        </div>
        <InsightsOpportunities />
      </div>
    </div>
  );
}
