/**
 * ChartCard — Pure SVG chart renderer for wealth advisory dashboard responses.
 * Supports: pie, bar, line chart types. Zero external chart libraries.
 */
import styles from "./ChartCard.module.css";

export interface ChartData {
  type: "pie" | "bar" | "line";
  title: string;
  labels: string[];
  values: number[];
  unit?: string; // e.g. "%" or "CHF"
}

// Colour palette aligned with dashboard theme
const PALETTE = [
  "#10a37f", // accent green
  "#1d4ed8", // blue
  "#7c3aed", // violet
  "#b45309", // amber
  "#0f766e", // teal
  "#dc2626", // red
  "#6d28d9", // purple
  "#065f46", // deep green
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

// ─── ChartCard (main export) ──────────────────────────────────────────────────

export function ChartCard({ data }: { data: ChartData }) {
  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <span className={styles.chartIcon}>
          {data.type === "pie" ? "◉" : data.type === "bar" ? "▦" : "〜"}
        </span>
        <h4 className={styles.cardTitle}>{data.title}</h4>
      </div>
      {data.type === "pie" && <PieChart data={data} />}
      {data.type === "bar" && <BarChart data={data} />}
      {data.type === "line" && <LineChart data={data} />}
    </div>
  );
}
