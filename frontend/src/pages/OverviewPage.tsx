import { Activity, ArrowRight, Bot, CalendarClock, UserRound } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { ChartCard, KpiCard } from "../components/charts/Charts";
import { Badge } from "../components/ui/Badge";
import { Card, CardHeader, PageHeader } from "../components/ui/Card";
import { Segmented } from "../components/ui/Misc";
import { EmptyState, ErrorState, Skeleton } from "../components/ui/States";
import { useAuth } from "../contexts/AuthContext";
import { useFilters } from "../contexts/FiltersContext";
import {
  ChannelsBlock,
  CoursesBlock,
  CoursesTable,
  DrilldownDrawer,
  FunnelBlock,
  FunnelTable,
  SourcesBlock,
  StatusBlock,
  TrendBlock,
  TrendTable,
  useOverview,
  type DrillTarget,
} from "../features/analytics";
import { cn } from "../lib/cn";
import { formatDayKey, formatTime, relativeTime, zoned, WEEKDAYS_SHORT } from "../lib/format";

const KPI_METRIC: Record<string, string> = {
  new_leads: "new_leads",
  new_conversations: "conversations",
  confirmed_bookings: "confirmed_bookings",
  attended: "attended",
  enrolled: "enrolled",
};

export function KpiGrid({ kpis, onDrill }: { kpis: import("../lib/types").Kpi[]; onDrill: (t: DrillTarget) => void }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {kpis.map((k) => (
        <KpiCard key={k.key} kpi={k} onClick={KPI_METRIC[k.key] ? () => onDrill({ title: k.label, metric: KPI_METRIC[k.key] }) : undefined} />
      ))}
    </div>
  );
}

export function KpiSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: 8 }).map((_, i) => (
        <Card key={i} className="p-4">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="mt-3 h-8 w-20" />
          <Skeleton className="mt-3 h-4 w-40" />
        </Card>
      ))}
    </div>
  );
}

const ACTOR_ICON: Record<string, typeof Bot> = { ai: Bot, user: UserRound, customer: UserRound, system: Activity };

export default function OverviewPage() {
  const { me } = useAuth();
  const { range, branchId } = useFilters();
  const [granularity, setGranularity] = useState<"day" | "week">("day");
  const [drill, setDrill] = useState<DrillTarget | null>(null);
  const params = { date_from: range.from, date_to: range.to, branch_id: branchId, granularity };
  const { data, isLoading, isError, error, refetch, isFetching } = useOverview(params);

  const hello = me?.full_name?.split(" ")[0];
  return (
    <>
      <PageHeader
        title="Umumiy ko'rinish"
        subtitle={
          <>
            {hello ? `Xush kelibsiz, ${hello}. ` : ""}
            {formatDayKey(range.from, { year: true })} – {formatDayKey(range.to, { year: true })}
            {data && <span className="text-ink-3"> · oldingi davr: {formatDayKey(data.period.previous_from)} – {formatDayKey(data.period.previous_to)}</span>}
          </>
        }
      />
      {isError && !data ? (
        <Card>
          <ErrorState error={error} onRetry={() => refetch()} />
        </Card>
      ) : isLoading || !data ? (
        <>
          <KpiSkeleton />
          <Card className="mt-4 p-5">
            <Skeleton className="h-[300px] w-full" />
          </Card>
        </>
      ) : (
        <div className={cn("space-y-4 transition-opacity", isFetching && "opacity-80")}>
          <KpiGrid kpis={data.kpis} onDrill={setDrill} />

          <div className="grid grid-cols-1 gap-4 2xl:grid-cols-3">
            <ChartCard
              className="2xl:col-span-2"
              title="Yangi mijozlar va tasdiqlangan bronlar"
              subtitle="Nuqtani bosing — o'sha davr mijozlari ro'yxati"
              empty={!data.timeseries.some((r) => r.new_leads || r.confirmed_bookings)}
              table={<TrendTable data={data.timeseries} />}
              actions={<Segmented label="Guruhlash" value={granularity} onChange={setGranularity} items={[{ value: "day", label: "Kun" }, { value: "week", label: "Hafta" }]} />}
            >
              <TrendBlock data={data} granularity={granularity} onDrill={setDrill} />
            </ChartCard>
            <ChartCard title="Mijozdan yozilishgacha" subtitle="Davrda kelgan mijozlar kohortasi" info="Har bir bosqich — davrda yaratilgan mijozlar ichida davr oxirigacha shu bosqichga yetgan noyob mijozlar. Qayta yozilish takror sanalmaydi." empty={!data.funnel[0]?.count} table={<FunnelTable data={data} />}>
              <FunnelBlock data={data} onDrill={setDrill} />
            </ChartCard>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <ChartCard title="Murojaat kanallari" subtitle="Yangi suhbatlar" empty={!data.channels.some((c) => c.count)}>
              <ChannelsBlock data={data} onDrill={setDrill} />
            </ChartCard>
            <ChartCard title="Mijoz manbalari" subtitle="Yangi mijozlar" empty={!data.sources.some((c) => c.count)}>
              <SourcesBlock data={data} onDrill={setDrill} />
            </ChartCard>
            <ChartCard title="Bronlar holati" subtitle="Davrda tasdiqlangan bronlar, joriy holat" empty={!data.booking_statuses.some((c) => c.count)}>
              <StatusBlock data={data} onDrill={setDrill} />
            </ChartCard>
          </div>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
            <ChartCard className="xl:col-span-1" title="Kurslar: qiziqish va bronlar" empty={!data.courses.some((c) => c.interest || c.bookings)} table={<CoursesTable data={data} />}>
              <CoursesBlock data={data} onDrill={setDrill} />
            </ChartCard>
            <Card className="flex flex-col">
              <CardHeader title="Yaqin sinov darslari" icon={<CalendarClock className="size-4" />} actions={<Link to="/bookings" className="inline-flex items-center gap-1 text-[13px] font-medium text-accent hover:underline">Kalendar <ArrowRight className="size-3.5" /></Link>} />
              <div className="px-5 pb-4">
                {data.upcoming_bookings.length === 0 ? (
                  <EmptyState title="Yaqin bronlar yo'q" className="py-6" />
                ) : (
                  <ul className="divide-y divide-line">
                    {data.upcoming_bookings.map((b) => {
                      const z = zoned(b.starts_at);
                      return (
                        <li key={b.booking_id}>
                          <Link to={`/bookings?booking=${b.booking_id}`} className="flex items-center gap-3 py-2.5 hover:bg-surface-2">
                            <span className="flex w-12 shrink-0 flex-col items-center rounded-lg border border-line bg-surface-2 py-1">
                              <span className="text-[11px] font-medium text-ink-3">{WEEKDAYS_SHORT[z.weekday]}</span>
                              <span className="text-[15px] leading-5 font-semibold text-ink tabular">{z.day}</span>
                            </span>
                            <span className="min-w-0 flex-1">
                              <span className="block truncate text-sm font-medium text-ink">{b.lead_name}</span>
                              <span className="block truncate text-[12px] text-ink-3">{b.course} · {b.branch}</span>
                            </span>
                            <Badge tone="accent">{formatTime(b.starts_at)}</Badge>
                          </Link>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            </Card>
            <Card className="flex flex-col">
              <CardHeader title="Oxirgi harakatlar" icon={<Activity className="size-4" />} />
              <div className="px-5 pb-4">
                {data.recent_activity.length === 0 ? (
                  <EmptyState title="Hozircha harakat yo'q" className="py-6" />
                ) : (
                  <ol className="relative space-y-3 border-l border-line pl-4">
                    {data.recent_activity.map((a) => {
                      const Icon = ACTOR_ICON[a.actor_type] ?? Activity;
                      return (
                        <li key={a.id} className="relative">
                          <span className="absolute top-0.5 -left-[25px] flex size-[18px] items-center justify-center rounded-full border border-line bg-surface text-ink-3">
                            <Icon className="size-3" aria-hidden />
                          </span>
                          <p className="text-[13px] leading-snug text-ink">{a.summary}</p>
                          <p className="text-[12px] text-ink-3">
                            {a.actor_name || { ai: "AI agent", customer: "Mijoz", system: "Tizim", user: "Xodim" }[a.actor_type]} · {relativeTime(a.created_at)}
                          </p>
                        </li>
                      );
                    })}
                  </ol>
                )}
              </div>
            </Card>
          </div>
        </div>
      )}
      <DrilldownDrawer params={params} target={drill} onClose={() => setDrill(null)} />
    </>
  );
}
