import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Ban, CalendarCheck, CircleCheck, MessageCircle, Send, UserX } from "lucide-react";
import { Link } from "react-router-dom";
import { CourseBars, DataTable, Funnel, HBars, Legend, TrendChart } from "../components/charts/Charts";
import { Badge } from "../components/ui/Badge";
import { Drawer } from "../components/ui/Overlay";
import { Pagination } from "../components/ui/Misc";
import { ErrorState, Skeleton } from "../components/ui/States";
import { get } from "../lib/api";
import { bookingStatusTone, leadStatusTone } from "../lib/constants";
import { formatDateTime, formatDayKey, formatNumber } from "../lib/format";
import type { Booking, ConversationItem, Lead, Overview, Paginated } from "../lib/types";
import { useState } from "react";

export interface AnalyticsParams {
  date_from: string;
  date_to: string;
  branch_id?: number | null;
  course_id?: number | null;
  source?: string | null;
  granularity?: "day" | "week" | "";
}

export function useOverview(params: AnalyticsParams) {
  return useQuery({
    queryKey: ["analytics", "overview", params],
    queryFn: () => get<Overview>("/analytics/overview/", { ...params, granularity: params.granularity || undefined }),
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });
}

export const TREND_SERIES = [
  { key: "new_leads", label: "Yangi mijozlar", color: "var(--series-1)", shape: "circle" as const },
  { key: "confirmed_bookings", label: "Tasdiqlangan bronlar", color: "var(--series-2)", shape: "square" as const },
];

export const STATUS_META: Record<string, { color: string; icon: React.ReactNode }> = {
  confirmed: { color: "var(--series-1)", icon: <CalendarCheck className="size-3.5 text-ink-3" aria-hidden /> },
  attended: { color: "var(--status-good)", icon: <CircleCheck className="size-3.5 text-ink-3" aria-hidden /> },
  no_show: { color: "var(--status-serious)", icon: <UserX className="size-3.5 text-ink-3" aria-hidden /> },
  cancelled: { color: "var(--status-critical)", icon: <Ban className="size-3.5 text-ink-3" aria-hidden /> },
};

export const CHANNEL_ICON: Record<string, React.ReactNode> = {
  telegram: <Send className="size-3.5 text-ink-3" aria-hidden />,
  webchat: <MessageCircle className="size-3.5 text-ink-3" aria-hidden />,
};

export interface DrillTarget {
  title: string;
  metric: string;
  bucket?: string;
  channel?: string;
  status?: string;
  stage?: string;
  detail_course_id?: number;
}

export function TrendTable({ data }: { data: Overview["timeseries"] }) {
  return (
    <DataTable
      columns={["Davr", "Yangi mijozlar", "Tasdiqlangan bronlar", "Bekor qilingan"]}
      rows={data.map((r) => [r.bucket_start === r.bucket_end ? formatDayKey(r.bucket) : `${formatDayKey(r.bucket_start)} – ${formatDayKey(r.bucket_end)}`, r.new_leads, r.confirmed_bookings, r.cancelled_bookings])}
    />
  );
}

export function TrendBlock({ data, granularity, onDrill }: { data: Overview; granularity: "day" | "week"; onDrill: (t: DrillTarget) => void }) {
  const totals = data.timeseries.reduce((acc, r) => ({ l: acc.l + r.new_leads, b: acc.b + r.confirmed_bookings }), { l: 0, b: 0 });
  return (
    <>
      <div className="mb-3">
        <Legend
          items={[
            { label: "Yangi mijozlar", color: "var(--series-1)", value: formatNumber(totals.l) },
            { label: "Tasdiqlangan bronlar", color: "var(--series-2)", shape: "square", value: formatNumber(totals.b) },
          ]}
        />
      </div>
      <TrendChart
        data={data.timeseries}
        series={TREND_SERIES}
        granularity={granularity}
        onPointClick={(bucket) => onDrill({ title: `Yangi mijozlar — ${formatDayKey(bucket)}${granularity === "week" ? " haftasi" : ""}`, metric: "new_leads", bucket })}
      />
    </>
  );
}

export function ChannelsBlock({ data, onDrill }: { data: Overview; onDrill: (t: DrillTarget) => void }) {
  return (
    <HBars
      items={data.channels.map((c, i) => ({ key: c.channel, label: c.label, value: c.count, color: i === 0 ? "var(--series-1)" : "var(--series-2)", icon: CHANNEL_ICON[c.channel], aria: c.label }))}
      onSelect={(channel) => onDrill({ title: `Suhbatlar — ${data.channels.find((c) => c.channel === channel)?.label}`, metric: "conversations", channel })}
    />
  );
}

export function SourcesBlock({ data, onDrill }: { data: Overview; onDrill: (t: DrillTarget) => void }) {
  return (
    <HBars
      items={data.sources.filter((s) => s.count > 0 || ["telegram", "webchat"].includes(s.source)).map((s) => ({ key: s.source, label: s.label, value: s.count, aria: s.label }))}
      onSelect={(source) => onDrill({ title: `Manba — ${data.sources.find((s) => s.source === source)?.label}`, metric: "sources", status: source })}
    />
  );
}

export function StatusBlock({ data, onDrill }: { data: Overview; onDrill: (t: DrillTarget) => void }) {
  return (
    <HBars
      items={data.booking_statuses.map((s) => ({ key: s.status, label: s.label, value: s.count, color: STATUS_META[s.status]?.color, icon: STATUS_META[s.status]?.icon, aria: s.label }))}
      onSelect={(status) => onDrill({ title: `Bronlar — ${data.booking_statuses.find((s) => s.status === status)?.label}`, metric: "booking_status", status })}
    />
  );
}

export function FunnelBlock({ data, onDrill }: { data: Overview; onDrill: (t: DrillTarget) => void }) {
  return <Funnel stages={data.funnel} onSelect={(stage) => onDrill({ title: `Funnel — ${data.funnel.find((f) => f.stage === stage)?.label}`, metric: "funnel", stage })} />;
}

export function CoursesBlock({ data, onDrill }: { data: Overview; onDrill: (t: DrillTarget) => void }) {
  return (
    <>
      <div className="mb-2">
        <Legend items={[{ label: "Qiziqish (yangi mijozlar)", color: "var(--series-1)", shape: "square" }, { label: "Tasdiqlangan bronlar", color: "var(--series-2)", shape: "square" }]} />
      </div>
      <CourseBars
        data={data.courses}
        onSelect={(courseId, series) => {
          const name = data.courses.find((c) => c.course_id === courseId)?.name;
          onDrill(
            series === "interest"
              ? { title: `${name} — qiziqqan mijozlar`, metric: "course_interest", detail_course_id: courseId }
              : { title: `${name} — bronlar`, metric: "course_bookings", detail_course_id: courseId },
          );
        }}
      />
    </>
  );
}

export function CoursesTable({ data }: { data: Overview }) {
  return <DataTable columns={["Kurs", "Qiziqish", "Bronlar"]} rows={data.courses.map((c) => [c.name, c.interest, c.bookings])} />;
}

export function FunnelTable({ data }: { data: Overview }) {
  return <DataTable columns={["Bosqich", "Mijozlar", "Kohortadan %"]} rows={data.funnel.map((f) => [f.label, f.count, f.rate === null ? "—" : `${f.rate}%`])} />;
}

export function DetailsRows({ kind, rows }: { kind: string; rows: (Lead | Booking | ConversationItem)[] }) {
  if (kind === "leads") {
    return (
      <ul className="divide-y divide-line">
        {(rows as Lead[]).map((l) => (
          <li key={l.id}>
            <Link to={`/leads?lead=${l.id}`} className="flex items-center justify-between gap-3 py-2.5 hover:bg-surface-2">
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium text-ink">{l.display_name}</span>
                <span className="block text-[12px] text-ink-3">
                  {l.source_label} · {l.interested_course_name || "kurs aniqlanmagan"} · {formatDateTime(l.created_at)}
                </span>
              </span>
              <Badge tone={leadStatusTone(l.status)} dot>
                {l.status_label}
              </Badge>
            </Link>
          </li>
        ))}
      </ul>
    );
  }
  if (kind === "bookings") {
    return (
      <ul className="divide-y divide-line">
        {(rows as Booking[]).map((b) => (
          <li key={b.id}>
            <Link to={`/bookings?booking=${b.id}`} className="flex items-center justify-between gap-3 py-2.5 hover:bg-surface-2">
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium text-ink">{b.lead_name}</span>
                <span className="block text-[12px] text-ink-3">
                  {b.course_name} · {b.branch_name} · {formatDateTime(b.starts_at)}
                </span>
              </span>
              <Badge tone={bookingStatusTone(b.status)} dot>
                {b.status_label}
              </Badge>
            </Link>
          </li>
        ))}
      </ul>
    );
  }
  return (
    <ul className="divide-y divide-line">
      {(rows as ConversationItem[]).map((c) => (
        <li key={c.id}>
          <Link to={`/conversations/${c.id}`} className="flex items-center justify-between gap-3 py-2.5 hover:bg-surface-2">
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium text-ink">{c.lead_name}</span>
              <span className="block truncate text-[12px] text-ink-3">{c.last_message_preview}</span>
            </span>
            <Badge tone={c.mode === "human" ? "warning" : "accent"}>{c.mode === "human" ? "Operator" : "AI"}</Badge>
          </Link>
        </li>
      ))}
    </ul>
  );
}

export function useDetails(params: AnalyticsParams, target: DrillTarget | null, page: number) {
  return useQuery({
    queryKey: ["analytics", "details", params, target, page],
    queryFn: () =>
      get<Paginated<Lead | Booking | ConversationItem> & { kind: string }>("/analytics/details/", {
        ...params,
        granularity: params.granularity || undefined,
        metric: target!.metric,
        bucket: target!.bucket,
        channel: target!.channel,
        status: target!.status,
        stage: target!.stage,
        detail_course_id: target!.detail_course_id,
        page,
        page_size: 10,
      }),
    enabled: !!target,
    placeholderData: keepPreviousData,
  });
}

export function DrilldownDrawer({ params, target, onClose }: { params: AnalyticsParams; target: DrillTarget | null; onClose: () => void }) {
  const [page, setPage] = useState(1);
  const query = useDetails(params, target, page);
  return (
    <Drawer open={!!target} onClose={() => { setPage(1); onClose(); }} title={target?.title ?? ""} subtitle={`${formatDayKey(params.date_from)} – ${formatDayKey(params.date_to)} · tanlangan filtrlar qo'llangan`}>
      {query.isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-11" />
          ))}
        </div>
      )}
      {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}
      {query.data && (
        <>
          {query.data.results.length === 0 ? (
            <p className="py-8 text-center text-sm text-ink-3">Bu segmentda yozuv yo'q.</p>
          ) : (
            <DetailsRows kind={query.data.kind} rows={query.data.results} />
          )}
          <div className="mt-4 border-t border-line pt-3">
            <Pagination page={query.data.page} totalPages={query.data.total_pages} count={query.data.count} onChange={setPage} />
          </div>
        </>
      )}
    </Drawer>
  );
}
