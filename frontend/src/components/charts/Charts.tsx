import { ArrowDownRight, ArrowUpRight, Minus, Table2 } from "lucide-react";
import { useId, useMemo, useState, type ReactNode } from "react";
import { Area, Bar, BarChart, CartesianGrid, ComposedChart, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { cn } from "../../lib/cn";
import { formatCompact, formatDayKey, formatKpiValue, formatNumber } from "../../lib/format";
import type { Kpi } from "../../lib/types";
import { Card, CardHeader } from "../ui/Card";
import { InfoTip } from "../ui/Misc";
import { EmptyState } from "../ui/States";

/* ------------------------------------------------------------------ Sparkline */
export function Sparkline({ data, height = 40 }: { data: { bucket: string; value: number | null }[]; height?: number }) {
  const last = [...data].reverse().find((d) => d.value !== null);
  const lastIndex = last ? data.lastIndexOf(last) : -1;
  const hasValues = data.some((d) => d.value !== null && d.value !== 0);
  if (!hasValues) return <div style={{ height }} className="flex items-end"><div className="h-px w-full bg-line" /></div>;
  return (
    <div style={{ height }} aria-hidden>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 6, right: 6, bottom: 4, left: 2 }}>
          <Line
            type="monotone"
            dataKey="value"
            stroke="var(--spark)"
            strokeWidth={2}
            isAnimationActive={false}
            connectNulls
            dot={(props: { cx?: number; cy?: number; index?: number }) =>
              props.index === lastIndex && props.cx !== undefined && props.cy !== undefined ? (
                <circle key="last" cx={props.cx} cy={props.cy} r={4} fill="var(--series-1)" stroke="var(--surface)" strokeWidth={2} />
              ) : (
                <g key={`d${props.index}`} />
              )
            }
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ------------------------------------------------------------------ KPI card */
export function DeltaChip({ kpi }: { kpi: Kpi }) {
  if (kpi.no_previous_data || kpi.change === null) {
    return <span className="text-[12px] text-ink-3">Oldingi davrda ma'lumot yo'q</span>;
  }
  const up = kpi.change > 0;
  const flat = kpi.change === 0;
  const good = flat ? null : kpi.lower_is_better ? !up : up;
  const Icon = flat ? Minus : up ? ArrowUpRight : ArrowDownRight;
  const unit = kpi.change_unit === "pp" ? " p.p." : "%";
  const sign = up ? "+" : flat ? "" : "−";
  return (
    <span className="inline-flex items-center gap-1.5 text-[12px]">
      <span
        className={cn(
          "inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 font-semibold tabular",
          good === true && "bg-success-soft text-success",
          good === false && "bg-danger-soft text-danger-strong",
          good === null && "bg-surface-3 text-ink-2",
        )}
      >
        <Icon className="size-3.5" aria-hidden />
        {sign}
        {Math.abs(kpi.change).toFixed(1).replace(/\.0$/, "")}
        {unit}
      </span>
      <span className="text-ink-3">oldingi davrga nisbatan</span>
    </span>
  );
}

export function KpiCard({ kpi, onClick }: { kpi: Kpi; onClick?: () => void }) {
  const prev = kpi.previous === null ? "—" : formatKpiValue(kpi.previous, kpi.unit);
  const description = `${kpi.label}: ${formatKpiValue(kpi.value, kpi.unit)}. Oldingi davr: ${prev}.`;
  const Comp = onClick ? "button" : "div";
  return (
    <Card className={cn("flex flex-col p-4 text-left", onClick && "transition-shadow hover:shadow-pop")}>
      <Comp {...(onClick ? { type: "button" as const, onClick, "aria-label": `${description} Tafsilotlarni ochish` } : {})} className="flex flex-1 flex-col text-left">
        <div className="flex items-center gap-1.5 text-[13px] font-medium text-ink-2">
          <span className="truncate">{kpi.label}</span>
          {kpi.definition && <InfoTip text={kpi.definition} />}
        </div>
        <div className="mt-2 flex items-end justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[26px] leading-8 font-semibold tracking-[-0.02em] whitespace-nowrap text-ink">{formatKpiValue(kpi.value, kpi.unit)}</p>
            {kpi.unit === "percent" && kpi.denominator !== undefined && (
              <p className="text-[12px] text-ink-3 tabular">
                {kpi.numerator}/{kpi.denominator} mijoz
              </p>
            )}
            {kpi.unit === "seconds" && kpi.samples !== undefined && <p className="text-[12px] text-ink-3 tabular">{kpi.samples} ta suhbat</p>}
          </div>
          <div className="w-[96px] min-w-[48px] shrink">
            <Sparkline data={kpi.sparkline} />
          </div>
        </div>
        <div className="mt-2 min-h-5">
          <DeltaChip kpi={kpi} />
        </div>
      </Comp>
    </Card>
  );
}

/* ------------------------------------------------------------------ Chart card + table view */
export function ChartCard({ title, subtitle, actions, table, children, empty, className, info }: { title: string; subtitle?: ReactNode; actions?: ReactNode; table?: ReactNode; children: ReactNode; empty?: boolean; className?: string; info?: string }) {
  const [showTable, setShowTable] = useState(false);
  return (
    <Card className={cn("flex flex-col", className)}>
      <CardHeader
        title={
          <span className="inline-flex items-center gap-1.5">
            {title}
            {info && <InfoTip text={info} />}
          </span>
        }
        subtitle={subtitle}
        actions={
          <>
            {actions}
            {table && !empty && (
              <button
                type="button"
                onClick={() => setShowTable((v) => !v)}
                aria-pressed={showTable}
                className={cn("inline-flex h-8 items-center gap-1.5 rounded-lg border px-2.5 text-[12px] font-medium", showTable ? "border-accent bg-accent-soft text-accent-ink" : "border-line text-ink-3 hover:text-ink")}
              >
                <Table2 className="size-3.5" aria-hidden />
                Jadval
              </button>
            )}
          </>
        }
      />
      <div className="flex-1 px-5 pb-5">
        {empty ? <EmptyState title="Tanlangan davrda ma'lumot yo'q" body="Filtrlarni o'zgartiring yoki boshqa davrni tanlang." className="py-8" /> : showTable && table ? table : children}
      </div>
    </Card>
  );
}

export function DataTable({ columns, rows }: { columns: string[]; rows: (string | number)[][] }) {
  return (
    <div className="scroll-thin max-h-[320px] overflow-auto rounded-lg border border-line">
      <table className="w-full text-[13px]">
        <thead className="sticky top-0 bg-surface-2 text-left text-ink-3">
          <tr>
            {columns.map((c) => (
              <th key={c} className="px-3 py-2 font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="tabular">
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-line">
              {r.map((cell, j) => (
                <td key={j} className={cn("px-3 py-1.5", j > 0 && "text-right")}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ------------------------------------------------------------------ Legend */
export function Legend({ items }: { items: { label: string; color: string; shape?: "circle" | "square"; value?: string }[] }) {
  return (
    <ul className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[12px] text-ink-2">
      {items.map((i) => (
        <li key={i.label} className="inline-flex items-center gap-2">
          <span className="relative inline-flex h-2 w-5 items-center" aria-hidden>
            <span className="h-0.5 w-full rounded" style={{ background: i.color }} />
            <span className={cn("absolute left-1/2 size-2 -translate-x-1/2", i.shape === "square" ? "rounded-[2px]" : "rounded-full")} style={{ background: i.color, boxShadow: "0 0 0 2px var(--surface)" }} />
          </span>
          {i.label}
          {i.value && <span className="font-semibold text-ink tabular">{i.value}</span>}
        </li>
      ))}
    </ul>
  );
}

/* ------------------------------------------------------------------ Trend chart (2 lines) */
interface TrendSeries {
  key: string;
  label: string;
  color: string;
  shape: "circle" | "square";
}

type TooltipProps = { active?: boolean; payload?: { dataKey?: string | number; value?: number; payload?: Record<string, unknown> }[]; label?: string };

function TrendTooltip({ active, payload, series, granularity }: TooltipProps & { series: TrendSeries[]; granularity: string }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload as { bucket_start: string; bucket_end: string } | undefined;
  if (!row) return null;
  const title = granularity === "week" ? `${formatDayKey(row.bucket_start)} – ${formatDayKey(row.bucket_end)}` : formatDayKey(row.bucket_start, { weekday: true, year: true });
  return (
    <div className="min-w-[180px] rounded-xl border border-line bg-surface px-3 py-2.5 text-[12px] shadow-pop">
      <p className="mb-1.5 font-semibold text-ink">{title}</p>
      {series.map((s) => {
        const item = payload.find((p) => p.dataKey === s.key);
        return (
          <div key={s.key} className="flex items-center justify-between gap-4 py-0.5">
            <span className="inline-flex items-center gap-2 text-ink-2">
              <span className={cn("size-2", s.shape === "square" ? "rounded-[2px]" : "rounded-full")} style={{ background: s.color }} aria-hidden />
              {s.label}
            </span>
            <span className="font-semibold text-ink tabular">{formatNumber(Number(item?.value ?? 0))}</span>
          </div>
        );
      })}
      <p className="mt-1.5 text-[11px] text-ink-3">Bosing — tafsilotlar jadvali</p>
    </div>
  );
}

export function TrendChart({ data, series, granularity, height = 300, onPointClick }: { data: Record<string, unknown>[]; series: TrendSeries[]; granularity: "day" | "week"; height?: number; onPointClick?: (bucket: string) => void }) {
  const gid = useId().replace(/:/g, "");
  const interval = useMemo(() => {
    if (data.length <= 10) return 0;
    return Math.ceil(data.length / 8) - 1;
  }, [data.length]);
  return (
    <div style={{ height }} className="w-full" role="img" aria-label={`Chiziqli grafik: ${series.map((s) => s.label).join(" va ")}. Batafsil qiymatlar uchun "Jadval" tugmasidan foydalaning.`}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart
          data={data}
          margin={{ top: 8, right: 12, bottom: 0, left: -12 }}
          onClick={(state: { activeLabel?: string | number; activeTooltipIndex?: number | string | null } | null) => {
            if (!onPointClick || !state) return;
            const idx = state.activeTooltipIndex;
            const row = idx !== undefined && idx !== null ? data[Number(idx)] : undefined;
            const bucket = (row?.bucket as string) || (state.activeLabel as string);
            if (bucket) onPointClick(bucket);
          }}
          style={{ cursor: onPointClick ? "pointer" : "default" }}
        >
          <defs>
            {series.map((s) => (
              <linearGradient key={s.key} id={`${gid}-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={s.color} stopOpacity={0.14} />
                <stop offset="100%" stopColor={s.color} stopOpacity={0.01} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid vertical={false} stroke="var(--grid)" strokeWidth={1} />
          <XAxis dataKey="bucket" tickFormatter={(v: string) => formatDayKey(v)} tickLine={false} axisLine={{ stroke: "var(--border)" }} interval={interval} tickMargin={8} minTickGap={8} />
          <YAxis allowDecimals={false} tickLine={false} axisLine={false} width={44} tickFormatter={(v: number) => formatCompact(v)} />
          <Tooltip cursor={{ stroke: "var(--border-strong)", strokeWidth: 1 }} content={<TrendTooltip series={series} granularity={granularity} />} />
          {series.map((s) => (
            <Area key={`a-${s.key}`} type="monotone" dataKey={s.key} stroke="none" fill={`url(#${gid}-${s.key})`} isAnimationActive={false} activeDot={false} tooltipType="none" />
          ))}
          {series.map((s) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.label}
              stroke={s.color}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
              activeDot={
                s.shape === "square"
                  ? (p: { cx?: number; cy?: number }) => <rect key="ad" x={(p.cx ?? 0) - 5} y={(p.cy ?? 0) - 5} width={10} height={10} rx={2} fill={s.color} stroke="var(--surface)" strokeWidth={2} />
                  : { r: 5, fill: s.color, stroke: "var(--surface)", strokeWidth: 2 }
              }
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ------------------------------------------------------------------ Horizontal bars (HTML) */
export function HBars({ items, color = "var(--series-1)", onSelect, total, showShare = true }: { items: { key: string; label: ReactNode; value: number; color?: string; icon?: ReactNode; aria?: string }[]; color?: string; onSelect?: (key: string) => void; total?: number; showShare?: boolean }) {
  const max = Math.max(1, ...items.map((i) => i.value));
  const sum = total ?? items.reduce((a, b) => a + b.value, 0);
  return (
    <ul className="flex flex-col gap-2.5">
      {items.map((i) => {
        const pct = sum ? Math.round((i.value / sum) * 1000) / 10 : 0;
        const content = (
          <>
            <div className="flex items-center justify-between gap-3 text-[13px]">
              <span className="inline-flex min-w-0 items-center gap-2 text-ink-2">
                {i.icon}
                <span className="truncate">{i.label}</span>
              </span>
              <span className="shrink-0 text-ink tabular">
                <span className="font-semibold">{formatNumber(i.value)}</span>
                {showShare && <span className="ml-1.5 text-ink-3">{pct}%</span>}
              </span>
            </div>
            <div className="mt-1.5 h-2 w-full rounded-full bg-surface-3" aria-hidden>
              <div className="h-2 rounded-full transition-[width]" style={{ width: `${(i.value / max) * 100}%`, background: i.color || color, minWidth: i.value ? 6 : 0 }} />
            </div>
          </>
        );
        return (
          <li key={i.key}>
            {onSelect ? (
              <button type="button" onClick={() => onSelect(i.key)} className="block w-full rounded-lg p-1 -m-1 text-left hover:bg-surface-2" title={`${i.aria ?? ""} ${formatNumber(i.value)} (${pct}%) — tafsilotlar`} aria-label={`${i.aria ?? ""}: ${i.value}, ${pct}%. Tafsilotlarni ko'rish`}>
                {content}
              </button>
            ) : (
              content
            )}
          </li>
        );
      })}
    </ul>
  );
}

/* ------------------------------------------------------------------ Funnel (ordinal ramp) */
export function Funnel({ stages, onSelect }: { stages: { stage: string; label: string; count: number; rate: number | null }[]; onSelect?: (stage: string) => void }) {
  const max = Math.max(1, stages[0]?.count ?? 1);
  const colors = ["var(--funnel-1)", "var(--funnel-2)", "var(--funnel-3)", "var(--funnel-4)", "var(--funnel-5)"];
  return (
    <ol className="flex flex-col gap-2">
      {stages.map((s, idx) => {
        const prev = idx > 0 ? stages[idx - 1].count : null;
        const step = prev ? Math.round((s.count / prev) * 1000) / 10 : null;
        return (
          <li key={s.stage}>
            <button
              type="button"
              onClick={() => onSelect?.(s.stage)}
              className="group flex w-full items-center gap-3 rounded-lg p-1 text-left hover:bg-surface-2"
              aria-label={`${s.label}: ${s.count} mijoz${s.rate !== null ? `, kohortaning ${s.rate}%` : ""}. Tafsilotlar`}
            >
              <span className="w-[132px] shrink-0 text-[13px] text-ink-2 sm:w-[150px]">{s.label}</span>
              <span className="relative h-7 flex-1 rounded-md bg-surface-3">
                <span className="absolute inset-y-0 left-0 rounded-md" style={{ width: `${Math.max(s.count ? 2 : 0, (s.count / max) * 100)}%`, background: colors[idx] }} />
              </span>
              <span className="w-[86px] shrink-0 text-right text-[13px] tabular">
                <span className="font-semibold text-ink">{formatNumber(s.count)}</span>
                <span className="ml-1 text-ink-3">{s.rate !== null ? `${s.rate}%` : "—"}</span>
              </span>
            </button>
            {step !== null && idx > 0 && <span className="sr-only">Oldingi bosqichdan o'tish: {step}%</span>}
          </li>
        );
      })}
    </ol>
  );
}

/* ------------------------------------------------------------------ Grouped bars (courses) */
function CourseTooltip({ active, payload }: TooltipProps) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload as { name: string; interest: number; bookings: number };
  return (
    <div className="rounded-xl border border-line bg-surface px-3 py-2.5 text-[12px] shadow-pop">
      <p className="mb-1 font-semibold text-ink">{row.name}</p>
      <p className="flex justify-between gap-6 text-ink-2">
        Qiziqish <span className="font-semibold text-ink tabular">{row.interest}</span>
      </p>
      <p className="flex justify-between gap-6 text-ink-2">
        Bronlar <span className="font-semibold text-ink tabular">{row.bookings}</span>
      </p>
    </div>
  );
}

export function CourseBars({ data, onSelect }: { data: { course_id: number; name: string; interest: number; bookings: number }[]; onSelect?: (courseId: number, series: "interest" | "bookings") => void }) {
  const height = Math.max(160, data.length * 56 + 24);
  return (
    <div style={{ height }} role="img" aria-label="Kurslar bo'yicha qiziqish va bronlar taqqoslanishi">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 24, bottom: 0, left: 0 }} barGap={2} barCategoryGap="28%">
          <CartesianGrid horizontal={false} stroke="var(--grid)" />
          <XAxis type="number" allowDecimals={false} tickLine={false} axisLine={false} />
          <YAxis type="category" dataKey="name" width={120} tickLine={false} axisLine={false} tick={{ fontSize: 12 }} />
          <Tooltip cursor={{ fill: "var(--surface-3)", opacity: 0.6 }} content={<CourseTooltip />} />
          <Bar dataKey="interest" name="Qiziqish" fill="var(--series-1)" radius={[0, 4, 4, 0]} maxBarSize={14} isAnimationActive={false} onClick={(d: { payload?: { course_id: number } }) => d.payload && onSelect?.(d.payload.course_id, "interest")} style={{ cursor: "pointer" }} />
          <Bar dataKey="bookings" name="Bronlar" fill="var(--series-2)" radius={[0, 4, 4, 0]} maxBarSize={14} isAnimationActive={false} onClick={(d: { payload?: { course_id: number } }) => d.payload && onSelect?.(d.payload.course_id, "bookings")} style={{ cursor: "pointer" }} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
