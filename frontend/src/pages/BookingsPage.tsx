import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ban, CalendarDays, CalendarPlus, ChevronLeft, ChevronRight, CircleCheck, List, MoveRight, UserX } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, PageHeader } from "../components/ui/Card";
import { Input, Select, Textarea } from "../components/ui/Form";
import { ConfirmDialog, Drawer } from "../components/ui/Overlay";
import { KeyValue, Pagination, Segmented } from "../components/ui/Misc";
import { EmptyState, ErrorState, Skeleton } from "../components/ui/States";
import { useFilters } from "../contexts/FiltersContext";
import { useToast } from "../contexts/ToastContext";
import { CreateBookingDialog, RescheduleDialog } from "../features/bookingDialogs";
import { errorMessage, get, post } from "../lib/api";
import { cn } from "../lib/cn";
import { BOOKING_STATUSES, bookingStatusTone } from "../lib/constants";
import { addDays, dateKey, formatDateTime, formatPhone, formatDayKey, formatTime, monthTitle, todayKey, WEEKDAYS_SHORT, weekdayOfKey, zoned } from "../lib/format";
import { useCourses } from "../lib/queries";
import type { Booking, Paginated, TrialSlot } from "../lib/types";

type CalView = "day" | "week" | "month";

function rangeFor(view: CalView, anchor: string): { from: string; to: string; days: string[] } {
  if (view === "day") return { from: anchor, to: anchor, days: [anchor] };
  if (view === "week") {
    const from = addDays(anchor, -weekdayOfKey(anchor));
    const days = Array.from({ length: 7 }, (_, i) => addDays(from, i));
    return { from, to: days[6], days };
  }
  const first = `${anchor.slice(0, 8)}01`;
  const gridStart = addDays(first, -weekdayOfKey(first));
  const days = Array.from({ length: 42 }, (_, i) => addDays(gridStart, i));
  return { from: days[0], to: days[41], days };
}

function slotTone(slot: TrialSlot) {
  if (slot.status === "cancelled") return "border-line bg-surface-3 text-ink-3 line-through";
  if (slot.seats_left === 0) return "border-[#fde68a] bg-warning-soft dark:border-[#4d3a12]";
  return "border-[#c7d2fe] bg-accent-soft dark:border-[#2e3577]";
}

function BookingChip({ b, onOpen }: { b: NonNullable<TrialSlot["bookings"]>[number]; onOpen: (id: number) => void }) {
  const Icon = b.status === "attended" ? CircleCheck : b.status === "no_show" ? UserX : null;
  return (
    <button type="button" onClick={() => onOpen(b.id)} className="flex w-full items-center gap-1 truncate rounded-md bg-surface px-1.5 py-0.5 text-left text-[11px] font-medium text-ink shadow-card hover:ring-1 hover:ring-accent" title={`${b.lead_name} — ${b.status}`}>
      {Icon && <Icon className="size-3 shrink-0 text-ink-3" aria-hidden />}
      <span className="truncate">{b.lead_name}</span>
    </button>
  );
}

function Calendar({ view, anchor, slots, onOpen }: { view: CalView; anchor: string; slots: TrialSlot[]; onOpen: (id: number) => void }) {
  const { days } = rangeFor(view, anchor);
  const today = todayKey();
  const byDay = useMemo(() => {
    const map = new Map<string, TrialSlot[]>();
    slots.forEach((s) => {
      const k = dateKey(s.starts_at);
      if (!map.has(k)) map.set(k, []);
      map.get(k)!.push(s);
    });
    map.forEach((list) => list.sort((a, b) => a.starts_at.localeCompare(b.starts_at)));
    return map;
  }, [slots]);

  if (view === "month") {
    const month = anchor.slice(0, 7);
    return (
      <div className="overflow-x-auto">
        <div className="grid min-w-[720px] grid-cols-7 border-t border-l border-line">
          {WEEKDAYS_SHORT.map((w) => (
            <div key={w} className="border-r border-b border-line bg-surface-2 px-2 py-1.5 text-[12px] font-medium text-ink-3">
              {w}
            </div>
          ))}
          {days.map((d) => {
            const list = byDay.get(d) ?? [];
            const bookings = list.flatMap((s) => s.bookings ?? []);
            return (
              <div key={d} className={cn("min-h-[104px] border-r border-b border-line p-1.5", d.slice(0, 7) !== month && "bg-surface-2/60")}>
                <p className={cn("mb-1 inline-flex size-6 items-center justify-center rounded-full text-[12px] font-semibold tabular", d === today ? "bg-accent text-white" : "text-ink-2")}>{Number(d.slice(8))}</p>
                {list.length > 0 && <p className="mb-1 text-[11px] text-ink-3">{list.length} slot · {bookings.length} bron</p>}
                <div className="space-y-0.5">
                  {bookings.slice(0, 3).map((b) => (
                    <BookingChip key={b.id} b={b} onOpen={onOpen} />
                  ))}
                  {bookings.length > 3 && <p className="text-[11px] text-ink-3">+{bookings.length - 3} ta</p>}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <div className={cn("grid gap-2", view === "week" ? "min-w-[860px] grid-cols-7" : "grid-cols-1")}>
        {days.map((d) => {
          const list = byDay.get(d) ?? [];
          return (
            <div key={d} className="min-w-0">
              <div className={cn("mb-2 flex items-center justify-between rounded-lg px-2 py-1.5", d === today ? "bg-accent-soft" : "bg-surface-2")}>
                <span className={cn("text-[13px] font-semibold", d === today ? "text-accent-ink" : "text-ink")}>{formatDayKey(d, { weekday: true })}</span>
                <span className="text-[11px] text-ink-3 tabular">{list.reduce((a, s) => a + (s.bookings?.length ?? 0), 0)} bron</span>
              </div>
              <div className="space-y-2">
                {list.length === 0 && <p className="px-2 py-4 text-center text-[12px] text-ink-3">Slot yo'q</p>}
                {list.map((s) => (
                  <div key={s.id} className={cn("rounded-xl border p-2", slotTone(s))}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[12px] font-semibold text-ink tabular">
                        {formatTime(s.starts_at)}–{formatTime(s.ends_at)}
                      </span>
                      <span className="text-[11px] text-ink-3 tabular" title="Band / sig'im">
                        {s.seats_taken}/{s.capacity}
                      </span>
                    </div>
                    <p className="truncate text-[12px] font-medium text-ink-2">{s.course_name}</p>
                    <p className="truncate text-[11px] text-ink-3">{s.branch_name}</p>
                    {(s.bookings?.length ?? 0) > 0 && (
                      <div className="mt-1.5 space-y-1">
                        {s.bookings!.map((b) => (
                          <BookingChip key={b.id} b={b} onOpen={onOpen} />
                        ))}
                      </div>
                    )}
                    {s.status === "cancelled" && <p className="mt-1 text-[11px]">Bekor qilingan</p>}
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function BookingDrawer({ id, onClose }: { id: number | null; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [cancelOpen, setCancelOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [reschedule, setReschedule] = useState<Booking | null>(null);
  const query = useQuery({ queryKey: ["booking", id], queryFn: () => get<Booking>(`/bookings/${id}/`), enabled: !!id });
  const b = query.data;
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["bookings"] });
    void qc.invalidateQueries({ queryKey: ["booking", id] });
    void qc.invalidateQueries({ queryKey: ["trial-slots"] });
    void qc.invalidateQueries({ queryKey: ["analytics"] });
  };
  const cancel = useMutation({
    mutationFn: () => post<Booking>(`/bookings/${id}/cancel/`, { reason }),
    onSuccess: () => { toast.success("Bron bekor qilindi", "Joy bo'shatildi, eslatma yuborilmaydi."); setCancelOpen(false); setReason(""); refresh(); },
    onError: (e) => toast.error("Bekor qilinmadi", errorMessage(e)),
  });
  const attendance = useMutation({
    mutationFn: (attended: boolean) => post<Booking>(`/bookings/${id}/attendance/`, { attended }),
    onSuccess: (r) => { toast.success("Qatnashuv belgilandi", r.status_label); refresh(); },
    onError: (e) => toast.error("Belgilanmadi", errorMessage(e)),
  });
  return (
    <Drawer
      open={!!id}
      onClose={onClose}
      title={b ? `Bron #${b.id}` : "Bron"}
      subtitle={b && <Badge tone={bookingStatusTone(b.status)} dot>{b.status_label}</Badge>}
      footer={
        b && (
          <>
            {b.status === "confirmed" && !b.can_mark_attendance && (
              <>
                <Button icon={<Ban className="size-4" />} onClick={() => setCancelOpen(true)}>
                  Bekor qilish
                </Button>
                <Button variant="primary" icon={<MoveRight className="size-4" />} onClick={() => setReschedule(b)}>
                  Ko'chirish
                </Button>
              </>
            )}
            {b.can_mark_attendance && b.status !== "cancelled" && (
              <>
                <Button icon={<UserX className="size-4" />} onClick={() => attendance.mutate(false)} loading={attendance.isPending && attendance.variables === false} disabled={b.status === "no_show"}>
                  Kelmadi
                </Button>
                <Button variant="primary" icon={<CircleCheck className="size-4" />} onClick={() => attendance.mutate(true)} loading={attendance.isPending && attendance.variables === true} disabled={b.status === "attended"}>
                  Qatnashdi
                </Button>
              </>
            )}
          </>
        )
      }
    >
      {query.isLoading && <Skeleton className="h-60" />}
      {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}
      {b && (
        <>
          <dl className="divide-y divide-line">
            <KeyValue label="Mijoz">
              <Link to={`/leads?lead=${b.lead_id}`} className="text-accent hover:underline">
                {b.lead_name}
              </Link>
            </KeyValue>
            <KeyValue label="Telefon">{formatPhone(b.lead_phone)}</KeyValue>
            <KeyValue label="Kurs">{b.course_name}</KeyValue>
            <KeyValue label="Guruh">{b.group_name}</KeyValue>
            <KeyValue label="Filial">{b.branch_name}</KeyValue>
            <KeyValue label="Vaqt">{`${formatDayKey(dateKey(b.starts_at), { weekday: true })}, ${formatTime(b.starts_at)}–${formatTime(b.ends_at)}`}</KeyValue>
            <KeyValue label="Kanal">{b.channel_label}</KeyValue>
            <KeyValue label="Tasdiqlangan">{formatDateTime(b.confirmed_at)}</KeyValue>
            {b.cancelled_at && <KeyValue label="Bekor qilingan">{`${formatDateTime(b.cancelled_at)}${b.cancel_reason ? ` · ${b.cancel_reason}` : ""}`}</KeyValue>}
            {b.reschedule_count > 0 && <KeyValue label="Ko'chirishlar">{b.reschedule_count}</KeyValue>}
            {b.notes && <KeyValue label="Izoh">{b.notes}</KeyValue>}
          </dl>
          {b.conversation_id && (
            <Link to={`/conversations/${b.conversation_id}`} className="mt-3 inline-flex text-[13px] font-medium text-accent hover:underline">
              Bron yaratilgan suhbatni ochish →
            </Link>
          )}
          <p className="mt-5 mb-2 text-[13px] font-medium text-ink-2">Hodisalar tarixi</p>
          <ol className="relative space-y-3 border-l border-line pl-4">
            {b.events?.map((e) => (
              <li key={e.id} className="relative">
                <span className="absolute top-1.5 -left-[21px] size-2.5 rounded-full border-2 border-surface bg-accent" aria-hidden />
                <p className="text-sm font-medium text-ink">{e.label}</p>
                <p className="text-[12px] text-ink-3">
                  {e.actor_name ?? { ai: "AI agent", user: "Xodim", system: "Tizim" }[e.actor_type] ?? e.actor_type} · {formatDateTime(e.occurred_at)}
                  {e.reason && ` · ${e.reason}`}
                </p>
              </li>
            ))}
          </ol>
          {b.status === "confirmed" && !b.can_mark_attendance && <p className="mt-4 rounded-lg bg-surface-2 px-3 py-2 text-[12px] text-ink-3">Qatnashuvni dars boshlangandan keyin belgilash mumkin.</p>}
        </>
      )}
      <ConfirmDialog
        open={cancelOpen}
        onClose={() => setCancelOpen(false)}
        onConfirm={() => cancel.mutate()}
        loading={cancel.isPending}
        danger
        title="Bronni bekor qilasizmi?"
        body="Joy boshqa mijozlar uchun bo'shatiladi va rejalashtirilgan eslatma bekor qilinadi. Bu amal statistikada bekor qilish hodisasi sifatida saqlanadi."
        confirmLabel="Bekor qilish"
      >
        <Textarea label="Sabab (ixtiyoriy)" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={255} />
      </ConfirmDialog>
      <RescheduleDialog booking={reschedule} onClose={() => setReschedule(null)} />
    </Drawer>
  );
}

function BookingList({ onOpen }: { onOpen: (id: number) => void }) {
  const { branchId } = useFilters();
  const { data: courses } = useCourses();
  const [status, setStatus] = useState("");
  const [course, setCourse] = useState("");
  const [from, setFrom] = useState(addDays(todayKey(), -14));
  const [to, setTo] = useState(addDays(todayKey(), 14));
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  useEffect(() => setPage(1), [status, course, from, to, search, branchId]);
  const query = useQuery({
    queryKey: ["bookings", "list", status, course, from, to, search, branchId, page],
    queryFn: () => get<Paginated<Booking>>("/bookings/", { status: status || undefined, course: course || undefined, date_from: from, date_to: to, search: search || undefined, branch: branchId ?? undefined, page, page_size: 15 }),
    placeholderData: keepPreviousData,
  });
  return (
    <>
      <div className="mb-3 grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-5">
        <Input aria-label="Qidirish" placeholder="Mijoz ismi yoki telefoni" value={search} onChange={(e) => setSearch(e.target.value)} />
        <Select aria-label="Holat" value={status} onChange={(e) => setStatus(e.target.value)} placeholder="Barcha holatlar" options={BOOKING_STATUSES} />
        <Select aria-label="Kurs" value={course} onChange={(e) => setCourse(e.target.value)} placeholder="Barcha kurslar" options={(courses ?? []).map((c) => ({ value: c.id, label: c.name }))} />
        <Input aria-label="Sanadan" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        <Input aria-label="Sanagacha" type="date" value={to} onChange={(e) => setTo(e.target.value)} />
      </div>
      {query.isError ? (
        <ErrorState error={query.error} onRetry={() => query.refetch()} />
      ) : query.isLoading ? (
        <Skeleton className="h-72" />
      ) : query.data!.results.length === 0 ? (
        <EmptyState title="Bron topilmadi" body="Sana oralig'ini yoki filtrlarni o'zgartiring." />
      ) : (
        <>
          <div className="overflow-x-auto rounded-xl border border-line">
            <table className="w-full min-w-[720px] text-sm">
              <thead className="bg-surface-2 text-left text-[12px] text-ink-3">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Vaqt</th>
                  <th className="px-3 py-2.5 font-medium">Mijoz</th>
                  <th className="px-3 py-2.5 font-medium">Kurs</th>
                  <th className="px-3 py-2.5 font-medium">Filial</th>
                  <th className="px-3 py-2.5 font-medium">Kanal</th>
                  <th className="px-4 py-2.5 font-medium">Holat</th>
                </tr>
              </thead>
              <tbody>
                {query.data!.results.map((b) => (
                  <tr key={b.id} className="cursor-pointer border-t border-line hover:bg-surface-2" onClick={() => onOpen(b.id)}>
                    <td className="px-4 py-2.5 whitespace-nowrap tabular">
                      <button type="button" className="text-left font-medium text-ink" onClick={(e) => { e.stopPropagation(); onOpen(b.id); }}>
                        {formatDayKey(dateKey(b.starts_at), { weekday: true })}, {formatTime(b.starts_at)}
                      </button>
                    </td>
                    <td className="px-3 py-2.5 text-ink">{b.lead_name}</td>
                    <td className="px-3 py-2.5 text-ink-2">{b.course_name}</td>
                    <td className="px-3 py-2.5 text-ink-2">{b.branch_name}</td>
                    <td className="px-3 py-2.5 text-ink-2">{b.channel_label}</td>
                    <td className="px-4 py-2.5"><Badge tone={bookingStatusTone(b.status)} dot>{b.status_label}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-3">
            <Pagination page={query.data!.page} totalPages={query.data!.total_pages} count={query.data!.count} onChange={setPage} />
          </div>
        </>
      )}
    </>
  );
}

export default function BookingsPage() {
  const [params, setParams] = useSearchParams();
  const { branchId } = useFilters();
  const { data: courses } = useCourses();
  const [mode, setMode] = useState<"calendar" | "list">("calendar");
  const [view, setView] = useState<CalView>(() => (window.innerWidth < 768 ? "day" : "week"));
  const [anchor, setAnchor] = useState(todayKey());
  const [course, setCourse] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const openId = Number(params.get("booking")) || null;
  const range = rangeFor(view, anchor);

  const query = useQuery({
    queryKey: ["trial-slots", "calendar", range.from, range.to, branchId, course],
    queryFn: () => get<{ results: TrialSlot[] }>("/trial-slots/calendar/", { date_from: range.from, date_to: range.to, branch: branchId ?? undefined, course: course || undefined }),
    placeholderData: keepPreviousData,
    enabled: mode === "calendar",
  });

  const setOpen = (id: number | null) => {
    const next = new URLSearchParams(params);
    if (id) next.set("booking", String(id));
    else next.delete("booking");
    setParams(next, { replace: true });
  };
  const step = view === "day" ? 1 : view === "week" ? 7 : 0;
  const move = (dir: -1 | 1) => {
    if (view === "month") {
      const [y, m] = anchor.split("-").map(Number);
      const d = new Date(Date.UTC(y, m - 1 + dir, 1));
      setAnchor(`${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-01`);
    } else setAnchor(addDays(anchor, dir * step));
  };
  const z = zoned(new Date(`${anchor}T12:00:00Z`));
  const title = view === "month" ? monthTitle(z.year, z.month) : view === "week" ? `${formatDayKey(range.from)} – ${formatDayKey(range.to, { year: true })}` : formatDayKey(anchor, { weekday: true, year: true });

  return (
    <>
      <PageHeader
        title="Sinov darslari"
        subtitle="Kalendar, bronlar va qatnashuv. Bo'sh joylar real vaqtda bazadan hisoblanadi."
        actions={
          <>
            <Segmented label="Ko'rinish" value={mode} onChange={setMode} items={[{ value: "calendar", label: "Kalendar", icon: <CalendarDays className="size-3.5" /> }, { value: "list", label: "Ro'yxat", icon: <List className="size-3.5" /> }]} />
            <Button variant="primary" icon={<CalendarPlus className="size-4" />} onClick={() => setCreateOpen(true)}>
              Bron yaratish
            </Button>
          </>
        }
      />
      <Card className="p-4">
        {mode === "calendar" ? (
          <>
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Button size="icon-sm" onClick={() => move(-1)} aria-label="Oldingi">
                  <ChevronLeft className="size-4" />
                </Button>
                <Button size="sm" onClick={() => setAnchor(todayKey())}>
                  Bugun
                </Button>
                <Button size="icon-sm" onClick={() => move(1)} aria-label="Keyingi">
                  <ChevronRight className="size-4" />
                </Button>
                <h2 className="ml-1 text-[15px] font-semibold text-ink" aria-live="polite">
                  {title}
                </h2>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Select aria-label="Kurs" className="min-w-[160px]" value={course} onChange={(e) => setCourse(e.target.value)} placeholder="Barcha kurslar" options={(courses ?? []).map((c) => ({ value: c.id, label: c.name }))} />
                <Segmented label="Kalendar ko'rinishi" value={view} onChange={setView} items={[{ value: "day", label: "Kun" }, { value: "week", label: "Hafta" }, { value: "month", label: "Oy" }]} />
              </div>
            </div>
            <div className="mb-3 flex flex-wrap gap-3 text-[12px] text-ink-3">
              <span className="inline-flex items-center gap-1.5"><span className="size-3 rounded border border-[#c7d2fe] bg-accent-soft" aria-hidden /> Bo'sh joy bor</span>
              <span className="inline-flex items-center gap-1.5"><span className="size-3 rounded border border-[#fde68a] bg-warning-soft" aria-hidden /> To'lgan</span>
              <span className="inline-flex items-center gap-1.5"><CircleCheck className="size-3" aria-hidden /> Qatnashdi</span>
              <span className="inline-flex items-center gap-1.5"><UserX className="size-3" aria-hidden /> Kelmadi</span>
            </div>
            {query.isError ? <ErrorState error={query.error} onRetry={() => query.refetch()} /> : query.isLoading ? <Skeleton className="h-96" /> : <Calendar view={view} anchor={anchor} slots={query.data!.results} onOpen={setOpen} />}
          </>
        ) : (
          <BookingList onOpen={setOpen} />
        )}
      </Card>
      <BookingDrawer id={openId} onClose={() => setOpen(null)} />
      <CreateBookingDialog open={createOpen} onClose={() => setCreateOpen(false)} />
    </>
  );
}
