import { useRef, useState } from "react";
import styles from "./PerformancePage.module.css";

interface PerformancePageProps {
  onAskQuestion: (question: string) => void;
  onBack: () => void;
}

// ─── Mock Data ───────────────────────────────────────────────────────────────

const PORTFOLIO_VALUE = [
  { month: "Oct", value: 54_200_000 },
  { month: "Nov", value: 56_500_000 },
  { month: "Dec", value: 55_745_000 },
  { month: "Jan", value: 58_900_000 },
  { month: "Feb", value: 62_100_000 },
  { month: "Mar", value: 65_000_000 },
];

const ASSET_ALLOCATION = [
  { label: "Equities", value: 48, color: "#da291c" },
  { label: "Fixed Income", value: 20, color: "#1e1e1e" },
  { label: "Private Equity", value: 14, color: "#ffd100" },
  { label: "Hedge Funds", value: 8, color: "#9b1318" },
  { label: "Structured Products", value: 6, color: "#b6b6b6" },
  { label: "Real Assets & Cash", value: 4, color: "#888888" },
];

const MONTHLY_RETURNS = [
  { month: "Oct", value: 2.1 },
  { month: "Nov", value: 3.6 },
  { month: "Dec", value: -1.9 },
  { month: "Jan", value: 4.0 },
  { month: "Feb", value: 2.7 },
  { month: "Mar", value: 2.8 },
];

const BENCHMARK_COMPARISON = [
  { month: "Oct", portfolio: 2.1, benchmark: 1.8 },
  { month: "Nov", portfolio: 3.6, benchmark: 2.5 },
  { month: "Dec", portfolio: -1.9, benchmark: -2.3 },
  { month: "Jan", portfolio: 4.0, benchmark: 3.1 },
  { month: "Feb", portfolio: 2.7, benchmark: 2.0 },
  { month: "Mar", portfolio: 2.8, benchmark: 1.9 },
];

// ─── Net Worth Mock Data ─────────────────────────────────────────────────────

const NET_WORTH_DATA = {
  asOf: "Mar 29, 2026",
  customer: "John Smith",
  customerId: "C-011",
  assets: {
    liquidAssets: [
      { label: "Personal Current Account (SGD)", value: 1_250_800, note: "SGD Main Account" },
      { label: "Multi-Currency Wealth Account", value: 5_280_000, note: "SGD + USD + EUR + CHF" },
      { label: "Investment Settlement Account", value: 1_940_000, note: "SGD Equivalent" },
      { label: "Liquidity Management Account", value: 3_300_000, note: "SGD Based" },
    ],
    investmentPortfolio: [
      { label: "Public Equities (48%)", value: 31_200_000, note: "Advisory + Discretionary" },
      { label: "Fixed Income (20%)", value: 13_000_000, note: "SGD + USD Bonds" },
      { label: "Private Equity / VC (14%)", value: 9_100_000, note: "Asia Growth Fund V" },
      { label: "Hedge Funds (8%)", value: 5_200_000, note: "Multi-strategy" },
      { label: "Structured Products (6%)", value: 3_900_000, note: "Yield Enhancement" },
      { label: "Real Asset Funds (2%)", value: 1_300_000, note: "Infrastructure" },
      { label: "Cash within Portfolio (2%)", value: 1_300_000, note: "Settlement buffer" },
    ],
    realEstate: [
      { label: "Sentosa Cove Villa, Singapore", value: 35_000_000, note: "SGD 35M" },
      { label: "GCB @ Nassim Road, Singapore", value: 65_000_000, note: "SGD 65M" },
      { label: "Niseko Ski Chalet, Japan", value: 4_500_000, note: "JPY 500M @ 0.009" },
    ],
    otherAssets: [
      { label: "Smith Capital SG Pte Ltd", value: 12_500_000, note: "Business equity" },
    ],
  },
  liabilities: [
    { label: "Residential Mortgage, Singapore", value: -12_500_000, note: "SGD 12.5M", rate: "3.85%" },
    { label: "Lombard Credit Facility (drawn)", value: -4_200_000, rate: "5.10%" },
    { label: "UBS Visa Infinite (outstanding)", value: -24_150, rate: "" },
    { label: "UBS Mastercard World Elite", value: -11_340, rate: "" },
  ],
};

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
    summary:
      "Your recent luxury vehicle acquisition includes significant ARF and COE exposure. A bespoke private client motor insurance arrangement is recommended, alongside a review of your fleet's COE renewal schedule to manage future cash outflows.",
    suggested_actions: [
      "Arrange agreed-value motor insurance for the Rolls-Royce Ghost (est. SGD 1.45M)",
      "Review PARF/COE rebate status for existing vehicles in your fleet due for replacement",
      "Explore UBS premium lifestyle partnership for bundled luxury asset cover including watch collections",
    ],
    rm_context:
      "Client acquired a Rolls-Royce Ghost (SGD 1.45M, 24 Mar 2026). Recommend motor insurance review and COE renewal management across his fleet.",
    tags: ["Insurance", "COE", "Vehicle"],
  },
  {
    id: "INS-002",
    priority: "medium",
    category: "Lifestyle & Memberships",
    icon: "⛳",
    title: "Exclusive Concierge Services for Sentosa Membership",
    trigger: "Sentosa Golf Club membership joins — SGD 650k on 18 Mar 2026",
    summary:
      "As a member of one of the world's premier clubs, you now have access to UBS's global lifestyle partnerships — including priority booking at Michelin-starred restaurants and private flight connections to regional courses.",
    suggested_actions: [
      "Connect with UBS Lifestyle Services for private culinary experiences at Capella or Marina Bay Sands",
      "Explore curated regional golf travel (Hokkaido, Danang, or Bali private courses)",
      "Inquire about exclusive member events co-hosted by UBS at Sentosa for networking with regional peers",
      "Explore premium equipment commissions through UBS retail partners for your new club membership",
    ],
    rm_context:
      "Client joined Sentosa Golf Club (SGD 650k, 18 Mar 2026). Opportunity to introduce Singapore-based lifestyle concierge and networking events.",
    tags: ["Lifestyle", "Concierge", "Networking"],
  },
  {
    id: "INS-003",
    priority: "high",
    category: "Art & Collectibles",
    icon: "🎨",
    title: "Art Finance & Collection Management for Zao Wou-Ki Acquisition",
    trigger: "Zao Wou-Ki painting acquired via Art SG — SGD 2.2M on 12 Mar 2026",
    summary:
      "Your recent acquisition of a material Zao Wou-Ki piece at Art SG represents a significant expansion of your collectible portfolio. UBS Art Advisory can assist with formal valuations and competitive art-backed lending facilities.",
    suggested_actions: [
      "Arrange fine art insurance with agreed value coverage (suggest Chubb Fine Art or MSIG)",
      "Explore art-backed lending through UBS Art Finance — unlocking liquidity at 40-60% LTV",
      "Engage UBS Art Advisory for formal collection documentation and inventory management",
      "Discuss provenance documentation and museum-grade storage arrangements in the Singapore FreePort",
    ],
    rm_context:
      "Client purchased a Zao Wou-Ki (SGD 2.2M, 12 Mar 2026). Recommend art insurance, art-backed lending, and collection management in the SG FreePort.",
    tags: ["Art Finance", "Insurance", "FreePort"],
  },
  {
    id: "INS-004",
    priority: "medium",
    category: "Currency & Liquidity",
    icon: "💱",
    title: "SGD Liquidity Rebalancing Post-Acquisitions",
    trigger: "Material drawdown of SGD cash balances (totaling SGD 3.65M over 2 weeks)",
    summary:
      "Recent high-value acquisitions have reduced your immediate SGD liquidity. Rather than direct FX conversion, you may wish to review your available Lombard facility or utilize our Liquidity Management Account (LMA) for smoothing.",
    suggested_actions: [
      "Review SGD and USD allocation within your Multi-Currency Account",
      "Consider drawing on your Lombard facility (SGD 10.8M available) for SGD cash flow smoothing",
      "Explore SGD-denominated money market funds via UBS Treasury for excess cash between capital calls",
      "Assess optimal currency composition for upcoming Niseko property stage payments",
    ],
    rm_context:
      "Significant SGD drawdown due to recent lifestyle purchases. Recommend Lombard utilization or cash flow optimization discussion.",
    tags: ["Liquidity", "Lombard", "Cash Management"],
  },
  {
    id: "INS-005",
    priority: "high",
    category: "Real Estate (Japan)",
    icon: "🏔️",
    title: "Niseko Chalet Acquisition — Cross-Border Financing",
    trigger: "Niseko Realty chalet deposit paid — SGD 580k on 8 Mar 2026",
    summary:
      "The commencement of a Niseko property acquisition suggests a need for bespoke cross-border financing. UBS can provide JPY-denominated lending secured against your SG-portfolio, as well as Japanese tax structuring advice.",
    suggested_actions: [
      "Initiate a UBS cross-border mortgage pre-assessment for the Niseko acquisition (JPY financing)",
      "Discuss holding structure options (direct ownership vs. Japanese GK structure)",
      "Review Japanese withholding tax and Singapore tax reporting requirements with UBS Tax team",
      "Assess hedging JPY stage payments against SGD/USD volatility",
    ],
    rm_context:
      "Client engaged for Niseko chalet acquisition (SGD 580k deposit, 8 Mar 2026). Recommend JPY-based cross-border lending and tax structuring discussion.",
    tags: ["Real Estate", "JPY Financing", "Tax", "Structuring"],
  },
  {
    id: "INS-006",
    priority: "medium",
    category: "Income & Tax",
    icon: "🇸🇬",
    title: "SRS & CPF Top-Up Opportunity for YA2027",
    trigger: "Recent SGD 850k dividend payment from Smith Capital SG Pte Ltd",
    summary:
      "Following your dividend receipt, we recommend reviewing your tax relief strategies before the 31 December deadline. Maximizing your SRS and CPF top-ups can provide immediate relief while enhancing long-term planning.",
    suggested_actions: [
      "Consider maximum SRS contribution (SGD 15,300 for residents) before 31 Dec to reduce taxable income",
      "Assess CPF Cash Top-up for you or your spouse for additional tax relief",
      "Explore SRS-approved investment strategies to optimize returns on idle SRS balances",
      "Review whether dividend funds should be deployed via the UBS Variable Capital Company (VCC) structure",
    ],
    rm_context:
      "Client received SGD 850k dividend (30 Jan 2026). Recommend SRS/CPF top-up discussion and VCC utilization before year-end tax planning cycle.",
    tags: ["Tax", "SRS", "CPF", "Retirement"],
  },
];

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

function NetWorthCalculator({ onAskQuestion }: { onAskQuestion: (context: string, suggestion: string) => void }) {
  const [expandedSection, setExpandedSection] = useState<string | null>(null);

  const totalLiquid = NET_WORTH_DATA.assets.liquidAssets.reduce((s, a) => s + a.value, 0);
  const totalPortfolio = NET_WORTH_DATA.assets.investmentPortfolio.reduce((s, a) => s + a.value, 0);
  const totalRealEstate = NET_WORTH_DATA.assets.realEstate.reduce((s, a) => s + a.value, 0);
  const totalOther = NET_WORTH_DATA.assets.otherAssets.reduce((s, a) => s + a.value, 0);
  const totalAssets = totalLiquid + totalPortfolio + totalRealEstate + totalOther;
  const totalLiabilities = NET_WORTH_DATA.liabilities.reduce((s, l) => s + Math.abs(l.value), 0);
  const netWorth = totalAssets - totalLiabilities;

  const assetSections = [
    {
      key: "liquid",
      label: "Liquid & Cash Assets",
      total: totalLiquid,
      color: "#da291c",
      items: NET_WORTH_DATA.assets.liquidAssets,
      icon: "💵",
      question: `My total liquid and cash assets are ${formatCurrency(totalLiquid)}. How does this liquidity position compare to what you'd recommend for someone with my profile?`,
    },
    {
      key: "portfolio",
      label: "Investment Portfolio (AUM)",
      total: totalPortfolio,
      color: "#1e1e1e",
      items: NET_WORTH_DATA.assets.investmentPortfolio,
      icon: "📈",
      question: `My investment portfolio with UBS is valued at ${formatCurrency(totalPortfolio)}. Can you give me a quick assessment of my current allocation and any rebalancing opportunities?`,
    },
    {
      key: "realestate",
      label: "Real Estate",
      total: totalRealEstate,
      color: "#9b1318",
      items: NET_WORTH_DATA.assets.realEstate,
      icon: "🏢",
      question: `My real estate holdings total ${formatCurrency(totalRealEstate)} across Singapore and Japan. What are your thoughts on my real estate exposure as a proportion of my net worth?`,
    },
    {
      key: "other",
      label: "Business & Other Assets",
      total: totalOther,
      color: "#ffd100",
      items: NET_WORTH_DATA.assets.otherAssets,
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
            Client: {NET_WORTH_DATA.customer} ({NET_WORTH_DATA.customerId}) · As of {NET_WORTH_DATA.asOf} · All values in SGD
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
              {NET_WORTH_DATA.liabilities.map((l) => (
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

function SummaryCards() {
  const currentValue = PORTFOLIO_VALUE[PORTFOLIO_VALUE.length - 1]!.value;
  const previousValue = PORTFOLIO_VALUE[0]!.value;
  const totalReturn = ((currentValue - previousValue) / previousValue * 100).toFixed(1);
  const ytdReturn = ((PORTFOLIO_VALUE[PORTFOLIO_VALUE.length - 1]!.value - PORTFOLIO_VALUE[2]!.value) / PORTFOLIO_VALUE[2]!.value * 100).toFixed(1);

  const cards = [
    { label: "Portfolio Value", value: formatCurrency(currentValue), sub: "As of Mar 2026 · John Smith (C-011)" },
    { label: "6M Return", value: `+${totalReturn}%`, sub: `+${formatCurrency(currentValue - previousValue)}` },
    { label: "YTD Return", value: `+${ytdReturn}%`, sub: "Jan - Mar 2026" },
    { label: "Risk Level", value: "Growth", sub: "Sharpe Ratio: 1.55" },
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

function PortfolioChart({ onClickPoint }: { onClickPoint: (context: string, suggestion: string) => void }) {
  const [hovered, setHovered] = useState<number | null>(null);
  const values = PORTFOLIO_VALUE.map((d) => d.value);
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
          const d = PORTFOLIO_VALUE[i]!;
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
                  `Why did my portfolio value ${d.value > PORTFOLIO_VALUE[0]!.value ? "increase" : "decrease"} to ${formatCurrency(d.value)} in ${d.month}? What were the key drivers?`,
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

function AllocationChart({ onClickSlice }: { onClickSlice: (context: string, suggestion: string) => void }) {
  const [hovered, setHovered] = useState<number | null>(null);
  const total = ASSET_ALLOCATION.reduce((s, d) => s + d.value, 0);
  const cx = 100;
  const cy = 100;
  const r = 85;

  let cumulative = 0;
  const slices = ASSET_ALLOCATION.map((d, i) => {
    const startAngle = (cumulative / total) * 360;
    cumulative += d.value;
    const endAngle = (cumulative / total) * 360;
    return { ...d, startAngle, endAngle, i };
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
          {ASSET_ALLOCATION.map((d, i) => (
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

function ReturnsChart({ onClickBar }: { onClickBar: (context: string, suggestion: string) => void }) {
  const [hovered, setHovered] = useState<number | null>(null);
  const maxVal = Math.max(...MONTHLY_RETURNS.map((d) => Math.abs(d.value)));
  const W = 500;
  const H = 200;
  const padLeft = 40;
  const padRight = 20;
  const padTop = 20;
  const padBottom = 36;
  const innerW = W - padLeft - padRight;
  const innerH = H - padTop - padBottom;
  const zeroY = padTop + innerH / 2;
  const barW = innerW / MONTHLY_RETURNS.length - 16;
  const gap = innerW / MONTHLY_RETURNS.length;

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
        {MONTHLY_RETURNS.map((d, i) => {
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
  onClose: () => void;
}

function RmNotifyPanel({ signal, onClose }: RmNotifyPanelProps) {
  const [sent, setSent] = useState(false);
  const [message, setMessage] = useState(
    `Dear Emma,\n\n${signal.rm_context}\n\nPlease could we discuss this at your earliest convenience?\n\nKind regards,\nJohn`,
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
        <div className={styles.rmPanelMeta}>Emma Clarke · emma.clarke@ubs.com · +44 20 7567 0100</div>
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
            <p className={styles.rmSentTitle}>Message sent to Emma Clarke</p>
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
              Send to Emma Clarke
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function InsightCard({ signal }: { signal: InsightSignal }) {
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
            {signal.tags.map((tag) => (
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
            {signal.suggested_actions.map((action, i) => (
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
            <RmNotifyPanel signal={signal} onClose={() => setShowRmPanel(false)} />
          )}
        </div>
      )}
    </div>
  );
}

function InsightsOpportunities() {
  const [filter, setFilter] = useState<"all" | "high" | "medium">("all");

  const filtered = filter === "all"
    ? INSIGHTS_SIGNALS
    : INSIGHTS_SIGNALS.filter((s) => s.priority === filter);

  const highCount = INSIGHTS_SIGNALS.filter((s) => s.priority === "high").length;
  const mediumCount = INSIGHTS_SIGNALS.filter((s) => s.priority === "medium").length;

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
            {f === "all" ? `All (${INSIGHTS_SIGNALS.length})` : f === "high" ? `Priority (${highCount})` : `Consider (${mediumCount})`}
          </button>
        ))}
      </div>

      <div className={styles.insightsList}>
        {filtered.map((signal) => (
          <InsightCard key={signal.id} signal={signal} />
        ))}
      </div>

      <p className={styles.insightsDisclaimer}>
        ⚠ All insights are generated from your activity data for informational purposes only. No actions are executed by the system. Please contact your Relationship Manager to discuss any of the above.
      </p>
    </div>
  );
}

// ─── Benchmark Comparison ────────────────────────────────────────────────────

function BenchmarkChart({ onClickPoint }: { onClickPoint: (context: string, suggestion: string) => void }) {
  const [hovered, setHovered] = useState<number | null>(null);
  const allValues = BENCHMARK_COMPARISON.flatMap((d) => [d.portfolio, d.benchmark]);
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
    return BENCHMARK_COMPARISON.map((d, i) => ({
      x: padLeft + (i / (BENCHMARK_COMPARISON.length - 1)) * innerW,
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
        <span className={styles.benchmarkKey}><span className={styles.legendDot} style={{ background: "#1e1e1e" }} /> Benchmark (S&P 500)</span>
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
        {portfolioPoints.map((p, i) => {
          const d = BENCHMARK_COMPARISON[i]!;
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
        {benchmarkPoints.map((p, i) => (
          <circle key={`b${i}`} cx={p.x} cy={p.y} r={3} fill="#1e1e1e" stroke="var(--color-bg)" strokeWidth={1.5} />
        ))}
      </svg>
    </div>
  );
}

// ─── Main Page ───────────────────────────────────────────────────────────────

export function PerformancePage({ onAskQuestion, onBack }: PerformancePageProps) {
  const [activeQuestion, setActiveQuestion] = useState<{ context: string; suggestion: string } | null>(null);

  function handleDataPointClick(context: string, suggestion: string) {
    setActiveQuestion({ context, suggestion });
  }

  function handleSendQuestion(question: string) {
    setActiveQuestion(null);
    onAskQuestion(question);
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
        <SummaryCards />

        {activeQuestion && (
          <QuestionPanel
            context={activeQuestion.context}
            suggestedQuestion={activeQuestion.suggestion}
            onSend={handleSendQuestion}
            onDismiss={() => setActiveQuestion(null)}
          />
        )}

        <NetWorthCalculator onAskQuestion={handleDataPointClick} />

        <div className={styles.chartsGrid}>
          <PortfolioChart onClickPoint={handleDataPointClick} />
          <AllocationChart onClickSlice={handleDataPointClick} />
          <ReturnsChart onClickBar={handleDataPointClick} />
          <BenchmarkChart onClickPoint={handleDataPointClick} />
        </div>

        <InsightsOpportunities />
      </div>
    </div>
  );
}

