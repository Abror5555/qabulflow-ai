import { Download, FilterX } from "lucide-react";
import { useState } from "react";
import { ChartCard } from "../components/charts/Charts";
import { Button } from "../components/ui/Button";
import { Card, PageHeader } from "../components/ui/Card";
import { Select } from "../components/ui/Form";
import { Segmented } from "../components/ui/Misc";
import { ErrorState, Skeleton } from "../components/ui/States";
import { useFilters } from "../contexts/FiltersContext";
import { useToast } from "../contexts/ToastContext";
import {
  ChannelsBlock,
  CoursesBlock,
  CoursesTable,
  DetailsRows,
  FunnelBlock,
  FunnelTable,
  SourcesBlock,
  StatusBlock,
  TrendBlock,
  TrendTable,
  useDetails,
  useOverview,
  type DrillTarget,
} from "../features/analytics";
import { buildQuery } from "../lib/api";
import { LEAD_SOURCES } from "../lib/constants";
import { daysBetween, formatDayKey } from "../lib/format";
import { useBranches, useCourses } from "../lib/queries";
import { KpiGrid, KpiSkeleton } from "./OverviewPage";
import { Pagination } from "../components/ui/Misc";
import { DateRangeControl } from "../components/layout/AppShell";

export default function AnalyticsPage() {
  const { range, branchId, setBranchId } = useFilters();
  const { data: branches } = useBranches();
  const { data: courses } = useCourses();
  const toast = useToast();
  const [courseId, setCourseId] = useState<number | null>(null);
  const [source, setSource] = useState<string>("");
  const longRange = daysBetween(range.from, range.to) > 62;
  const [granularity, setGranularity] = useState<"day" | "week">(longRange ? "week" : "day");
  const [detailTarget, setDetailTarget] = useState<DrillTarget>({ title: "Yangi mijozlar", metric: "new_leads" });
  const [detailPage, setDetailPage] = useState(1);
  const params = { date_from: range.from, date_to: range.to, branch_id: branchId, course_id: courseId, source: source || null, granularity };
  const { data, isLoading, isError, error, refetch } = useOverview(params);
  const details = useDetails(params, detailTarget, detailPage);

  const drillToTable = (t: DrillTarget) => {
    setDetailTarget(t);
    setDetailPage(1);
    window.requestAnimationFrame(() => document.getElementById("analytics-details")?.scrollIntoView({ behavior: "smooth", block: "start" }));
  };

  const exportCsv = () => {
    const qs = buildQuery({ ...params, granularity });
    const a = document.createElement("a");
    a.href = `/api/analytics/export.csv${qs}`;
    a.rel = "noopener";
    a.click();
    toast.success("CSV eksport tayyorlanmoqda", "Fayl panel bilan bir xil filtrlar asosida yuklanadi.");
  };

  const filtersActive = !!(branchId || courseId || source);

  return (
    <>
      <PageHeader
        title="Analitika"
        subtitle={`${formatDayKey(range.from, { year: true })} – ${formatDayKey(range.to, { year: true })} · barcha qiymatlar bazadagi yozuvlardan, tashkilot vaqt zonasida hisoblanadi`}
        actions={
          <Button variant="primary" icon={<Download className="size-4" />} onClick={exportCsv}>
            CSV eksport
          </Button>
        }
      />
      <Card className="mb-4 p-3">
        <div className="flex flex-wrap items-end gap-2.5">
          <div className="flex flex-col gap-1.5">
            <span className="text-[12px] font-medium text-ink-3">Davr</span>
            <DateRangeControl alwaysLabel />
          </div>
          <Select label="Filial" className="min-w-[170px]" value={branchId ?? ""} onChange={(e) => setBranchId(e.target.value ? Number(e.target.value) : null)} placeholder="Barcha filiallar" options={(branches ?? []).map((b) => ({ value: b.id, label: b.name }))} />
          <Select label="Kurs" className="min-w-[170px]" value={courseId ?? ""} onChange={(e) => setCourseId(e.target.value ? Number(e.target.value) : null)} placeholder="Barcha kurslar" options={(courses ?? []).map((c) => ({ value: c.id, label: c.name }))} />
          <Select label="Manba" className="min-w-[150px]" value={source} onChange={(e) => setSource(e.target.value)} placeholder="Barcha manbalar" options={LEAD_SOURCES} />
          <div className="flex flex-col gap-1.5">
            <span className="text-[12px] font-medium text-ink-3">Guruhlash</span>
            <Segmented label="Guruhlash" value={granularity} onChange={setGranularity} items={[{ value: "day", label: "Kun" }, { value: "week", label: "Hafta" }]} />
          </div>
          {filtersActive && (
            <Button variant="ghost" icon={<FilterX className="size-4" />} onClick={() => { setBranchId(null); setCourseId(null); setSource(""); }}>
              Filtrlarni tozalash
            </Button>
          )}
        </div>
      </Card>

      {isError && !data ? (
        <Card>
          <ErrorState error={error} onRetry={() => refetch()} />
        </Card>
      ) : isLoading || !data ? (
        <>
          <KpiSkeleton />
          <Card className="mt-4 p-5">
            <Skeleton className="h-[340px]" />
          </Card>
        </>
      ) : (
        <div className="space-y-4">
          <KpiGrid kpis={data.kpis} onDrill={drillToTable} />
          <ChartCard
            title="Yangi mijozlar va tasdiqlangan bronlar"
            subtitle={granularity === "week" ? "Haftalik (dushanbadan boshlanadi)" : "Kunlik"}
            empty={!data.timeseries.some((r) => r.new_leads || r.confirmed_bookings)}
            table={<TrendTable data={data.timeseries} />}
          >
            <TrendBlock data={data} granularity={granularity} onDrill={drillToTable} />
          </ChartCard>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <ChartCard title="Kurslar bo'yicha qiziqish va bronlar" empty={!data.courses.some((c) => c.interest || c.bookings)} table={<CoursesTable data={data} />}>
              <CoursesBlock data={data} onDrill={drillToTable} />
            </ChartCard>
            <ChartCard title="Funnel: mijozdan o'qishga yozilishgacha" info="Kohorta: davrda yaratilgan noyob mijozlar. Bosqichlar hodisalar tarixidan davr oxirigacha hisoblanadi; bir mijoz ikki marta sanalmaydi." empty={!data.funnel[0]?.count} table={<FunnelTable data={data} />}>
              <FunnelBlock data={data} onDrill={drillToTable} />
            </ChartCard>
          </div>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <ChartCard title="Kanallar" subtitle="Telegram va veb-chat suhbatlari" empty={!data.channels.some((c) => c.count)}>
              <ChannelsBlock data={data} onDrill={drillToTable} />
            </ChartCard>
            <ChartCard title="Manbalar" subtitle="Yangi mijozlar" empty={!data.sources.some((c) => c.count)}>
              <SourcesBlock data={data} onDrill={drillToTable} />
            </ChartCard>
            <ChartCard title="Bronlar holati" empty={!data.booking_statuses.some((c) => c.count)}>
              <StatusBlock data={data} onDrill={drillToTable} />
            </ChartCard>
          </div>
          <Card id="analytics-details" className="scroll-mt-24">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-5 py-3.5">
              <div>
                <h2 className="text-[15px] font-semibold text-ink">Tafsilotlar: {detailTarget.title}</h2>
                <p className="text-[13px] text-ink-3">Grafik nuqtasi yoki segmentini bosing — jadval shu tanlovga filtrlanadi</p>
              </div>
            </div>
            <div className="px-5 py-2">
              {details.isLoading ? (
                <Skeleton className="my-3 h-40" />
              ) : details.data && details.data.results.length ? (
                <DetailsRows kind={details.data.kind} rows={details.data.results} />
              ) : (
                <p className="py-8 text-center text-sm text-ink-3">Tanlangan segmentda yozuv yo'q.</p>
              )}
            </div>
            {details.data && (
              <div className="border-t border-line px-5 py-3">
                <Pagination page={details.data.page} totalPages={details.data.total_pages} count={details.data.count} onChange={setDetailPage} />
              </div>
            )}
          </Card>
        </div>
      )}
    </>
  );
}
