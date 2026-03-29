/**
 * ChartCard — Pure SVG chart renderer for wealth advisory dashboard responses.
 * Supports: pie, bar, line chart types. Zero external chart libraries.
 */
import styles from "./ChartCard.module.css";

export interface ChartData {
  type: "pie" | "bar" | "line" | "gauge";
  title: string;
  labels: string[];
  values: number[];
  unit?: string; // e.g. "%" or "CHF"
  badge?: string; // e.g. "Sufficient" for gauge charts
}

// Colour palette aligned with dashboard theme
const PALETTE = [
  "#da291c", // red (prioritised)
  "#ffd100", // yellow
  "#1e1e1e", // black
  "#9b1318", // dark red
  "#b6b6b6", // medium gray
  "#282828", // dark gray
  "#f2f2f2", // light gray
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function pieSlicePath(
  cx: number,
  cy: number,
  r: number,
  startAngle: number,
  endAngle: number,
): string {
  const start = polarToCartesian(cx, cy, r, endAngle);
  const end = polarToCartesian(cx, cy, r, startAngle);
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;
  return [
    `M ${cx} ${cy}`,
    `L ${start.x} ${start.y}`,
    `A ${r} ${r} 0 ${largeArc} 0 ${end.x} ${end.y}`,
    "Z",
  ].join(" ");
}

// ─── Pie Chart ────────────────────────────────────────────────────────────────

function PieChart({ data }: { data: ChartData }) {
  const total = data.values.reduce((s, v) => s + v, 0);
  const cx = 90;
  const cy = 90;
  const r = 75;

  let cumulative = 0;
  const slices = data.values.map((v, i) => {
    const startAngle = (cumulative / total) * 360;
    cumulative += v;
    const endAngle = (cumulative / total) * 360;
    return { startAngle, endAngle, color: PALETTE[i % PALETTE.length]!, label: data.labels[i]!, value: v };
  });

  return (
    <div className={styles.chartInner}>
      <svg viewBox="0 0 180 180" className={styles.pieSvg} aria-hidden="true">
        {slices.map((s, i) => (
          <path
            key={i}
            d={pieSlicePath(cx, cy, r, s.startAngle, s.endAngle)}
            fill={s.color}
            stroke="var(--color-bg)"
            strokeWidth={1.5}
            className={styles.slice}
          >
            <title>{`${s.label}: ${s.value}${data.unit ?? "%"}`}</title>
          </path>
        ))}
        {/* Donut hole */}
        <circle cx={cx} cy={cy} r={38} fill="var(--color-bg)" />
        <text x={cx} y={cy - 6} textAnchor="middle" className={styles.donutLabel}>
          {total}
        </text>
        <text x={cx} y={cy + 10} textAnchor="middle" className={styles.donutSub}>
          {data.unit ?? "%"}
        </text>
      </svg>
      <Legend data={data} />
    </div>
  );
}

// ─── Bar Chart ────────────────────────────────────────────────────────────────

function BarChart({ data }: { data: ChartData }) {
  const maxVal = Math.max(...data.values);
  const W = 280;
  const H = 140;
  const padLeft = 32;
  const padBottom = 28;
  const innerW = W - padLeft - 8;
  const innerH = H - padBottom - 8;
  const barW = Math.max(12, innerW / data.values.length - 6);
  const gap = innerW / data.values.length;

  return (
    <div className={styles.chartInner}>
      <svg viewBox={`0 0 ${W} ${H}`} className={styles.barSvg} aria-hidden="true">
        {/* Y-axis gridlines */}
        {[0, 0.25, 0.5, 0.75, 1].map((frac) => {
          const y = 8 + innerH * (1 - frac);
          return (
            <g key={frac}>
              <line x1={padLeft} y1={y} x2={W - 8} y2={y} stroke="var(--color-border)" strokeWidth={0.5} />
              <text x={padLeft - 4} y={y + 3} textAnchor="end" className={styles.axisLabel}>
                {Math.round(maxVal * frac)}
              </text>
            </g>
          );
        })}
        {/* Bars */}
        {data.values.map((v, i) => {
          const barH = (v / maxVal) * innerH;
          const x = padLeft + gap * i + (gap - barW) / 2;
          const y = 8 + innerH - barH;
          const color = PALETTE[i % PALETTE.length];
          return (
            <g key={i}>
              <rect
                x={x} y={y} width={barW} height={barH}
                fill={color} rx={3}
                className={styles.bar}
              >
                <title>{`${data.labels[i]!}: ${v}${data.unit ?? ""}`}</title>
              </rect>
              <text
                x={x + barW / 2}
                y={H - padBottom + 12}
                textAnchor="middle"
                className={styles.axisLabel}
              >
                {(data.labels[i]!).length > 6 ? (data.labels[i]!).slice(0, 5) + "…" : data.labels[i]!}
              </text>
            </g>
          );
        })}
        {/* X-axis line */}
        <line x1={padLeft} y1={8 + innerH} x2={W - 8} y2={8 + innerH} stroke="var(--color-border)" strokeWidth={1} />
      </svg>
      <Legend data={data} />
    </div>
  );
}

// ─── Line Chart ───────────────────────────────────────────────────────────────

function LineChart({ data }: { data: ChartData }) {
  const maxVal = Math.max(...data.values);
  const minVal = Math.min(...data.values);
  const range = maxVal - minVal || 1;
  const W = 280;
  const H = 140;
  const padLeft = 36;
  const padBottom = 28;
  const innerW = W - padLeft - 8;
  const innerH = H - padBottom - 8;

  const points = data.values.map((v, i) => ({
    x: padLeft + (i / (data.values.length - 1 || 1)) * innerW,
    y: 8 + innerH - ((v - minVal) / range) * innerH,
    v,
  }));
  const polyline = points.map((p) => `${p.x},${p.y}`).join(" ");

  return (
    <div className={styles.chartInner}>
      <svg viewBox={`0 0 ${W} ${H}`} className={styles.lineSvg} aria-hidden="true">
        {/* Gridlines */}
        {[0, 0.5, 1].map((frac) => {
          const y = 8 + innerH * (1 - frac);
          const val = minVal + range * frac;
          return (
            <g key={frac}>
              <line x1={padLeft} y1={y} x2={W - 8} y2={y} stroke="var(--color-border)" strokeWidth={0.5} strokeDasharray="3 3" />
              <text x={padLeft - 4} y={y + 3} textAnchor="end" className={styles.axisLabel}>
                {Math.round(val)}{data.unit ?? ""}
              </text>
            </g>
          );
        })}
        {/* Shaded fill */}
        <polygon
          points={`${padLeft},${8 + innerH} ${polyline} ${points[points.length - 1]!.x},${8 + innerH}`}
          fill={PALETTE[0]}
          fillOpacity={0.08}
        />
        {/* Line */}
        <polyline points={polyline} fill="none" stroke={PALETTE[0]} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        {/* Dots + labels */}
        {points.map((p, i) => (
          <g key={i}>
            <circle cx={p.x} cy={p.y} r={3.5} fill={PALETTE[0]} stroke="var(--color-bg)" strokeWidth={1.5} className={styles.dot}>
              <title>{`${data.labels[i]!}: ${p.v}${data.unit ?? ""}`}</title>
            </circle>
            <text x={p.x} y={H - padBottom + 12} textAnchor="middle" className={styles.axisLabel}>
              {(data.labels[i]!).length > 5 ? (data.labels[i]!).slice(0, 4) + "…" : data.labels[i]!}
            </text>
          </g>
        ))}
        {/* X-axis */}
        <line x1={padLeft} y1={8 + innerH} x2={W - 8} y2={8 + innerH} stroke="var(--color-border)" strokeWidth={1} />
      </svg>
      <Legend data={data} />
    </div>
  );
}

// ─── Legend ───────────────────────────────────────────────────────────────────

function Legend({ data }: { data: ChartData }) {
  const total = data.values.reduce((s, v) => s + v, 0);
  return (
    <div className={styles.legend}>
      {data.labels.map((label, i) => {
        const pct = total > 0 ? ((data.values[i]! / total) * 100).toFixed(1) : "—";
        return (
          <div key={i} className={styles.legendItem}>
            <span className={styles.legendDot} style={{ background: PALETTE[i % PALETTE.length] }} />
            <span className={styles.legendLabel}>{label}</span>
            <span className={styles.legendValue}>
              {data.values[i]}{data.unit ?? "%"}
              {data.type === "pie" && <span className={styles.legendPct}> ({pct}%)</span>}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ─── Gauge Chart ──────────────────────────────────────────────────────────────

function GaugeChart({ data }: { data: ChartData }) {
  const cx = 140;
  const cy = 135;
  const r = 90;
  
  const value = data.values[0] || 0;
  const max = data.values[1] || Math.max(value * 1.5, 1);
  const ratio = Math.min(Math.max(value / max, 0), 1);
  const angleDeg = -180 + (ratio * 180); // -180 is left, 0 is right
  
  const start = polarToCartesian(cx, cy, r, -180);
  const end = polarToCartesian(cx, cy, r, angleDeg);
  const fullEnd = polarToCartesian(cx, cy, r, 0);
  
  const trackPath = `M ${start.x} ${start.y} A ${r} ${r} 0 0 1 ${fullEnd.x} ${fullEnd.y}`;
  const fillPath = ratio > 0 ? `M ${start.x} ${start.y} A ${r} ${r} 0 0 1 ${end.x} ${end.y}` : "";
  
  // Track starts grey, turns yellow, then red. We'll use Red for majority of good track.
  const fillColor = ratio > 0.8 ? PALETTE[0] : (ratio > 0.5 ? PALETTE[1] : PALETTE[4]);
  
  return (
    <div className={styles.chartInner} style={{ flexDirection: "column", alignItems: "center", position: "relative" }}>
      <svg viewBox="0 0 280 150" className={styles.barSvg} aria-hidden="true">
        {/* Background track */}
        <path d={trackPath} fill="none" stroke="var(--color-border)" strokeWidth={16} strokeLinecap="round" />
        
        {/* Filled track */}
        {ratio > 0 && (
          <path d={fillPath} fill="none" stroke={fillColor} strokeWidth={16} strokeLinecap="round" className={styles.slice} />
        )}
        
        {/* Center Value */}
        <text x={cx} y={cy - 25} textAnchor="middle" style={{ fontSize: "28px", fontWeight: "bold", fill: "var(--color-text-primary)", fontFamily: "inherit" }}>
          {value.toLocaleString('en-US').replace(/,/g, "'")}
        </text>
        
        {/* Sub Label */}
        {data.labels[0] && (
          <text x={cx} y={cy + 2} textAnchor="middle" style={{ fontSize: "11px", fill: "var(--color-text-secondary)", fontFamily: "inherit" }}>
            {data.labels[0]}
          </text>
        )}
      </svg>
      
      {/* Badge container below svg */}
      {data.badge && (
        <div style={{
          marginTop: "-15px",
          padding: "4px 14px",
          background: "var(--color-bg-secondary)",
          border: "1px solid var(--color-border)",
          borderRadius: "16px",
          fontSize: "11px",
          fontWeight: 600,
          color: "var(--color-text-primary)"
        }}>
          {data.badge}
        </div>
      )}
    </div>
  );
}

// ─── ChartCard (main export) ──────────────────────────────────────────────────

export function ChartCard({ data }: { data: ChartData }) {
  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <span className={styles.chartIcon}>
          {data.type === "pie" ? "◉" : data.type === "bar" ? "▦" : data.type === "gauge" ? "◒" : "〜"}
        </span>
        <h4 className={styles.cardTitle}>{data.title}</h4>
      </div>
      {data.type === "pie" && <PieChart data={data} />}
      {data.type === "bar" && <BarChart data={data} />}
      {data.type === "line" && <LineChart data={data} />}
      {data.type === "gauge" && <GaugeChart data={data} />}
    </div>
  );
}
