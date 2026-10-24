import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarPlus, GraduationCap, KanbanSquare, List, MessageSquare, Phone, Plus, Search, Send, SlidersHorizontal, UserPlus } from "lucide-react";
import { useEffect, useMemo, useState, type DragEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, PageHeader } from "../components/ui/Card";
import { Input, Select, Textarea } from "../components/ui/Form";
import { Dialog, Drawer } from "../components/ui/Overlay";
import { Avatar, KeyValue, Pagination, Segmented, Tabs } from "../components/ui/Misc";
import { EmptyState, ErrorState, Skeleton } from "../components/ui/States";
import { useAuth } from "../contexts/AuthContext";
import { useFilters } from "../contexts/FiltersContext";
import { useToast } from "../contexts/ToastContext";
import { CreateBookingDialog } from "../features/bookingDialogs";
import { ApiError, errorMessage, get, patch, post } from "../lib/api";
import { cn } from "../lib/cn";
import { bookingStatusTone, LANGUAGES, LEAD_SOURCES, LEAD_STATUSES, leadStatusTone } from "../lib/constants";
import { formatDateTime, formatPhone, relativeTime } from "../lib/format";
import { useAssignable, useBranches, useCourses, useGroups } from "../lib/queries";
import type { Enrollment, Lead, LeadDetail, LeadStatus, Paginated } from "../lib/types";

type View = "table" | "kanban";

function useInvalidateLeads() {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: ["leads"] });
    void qc.invalidateQueries({ queryKey: ["lead"] });
    void qc.invalidateQueries({ queryKey: ["analytics"] });
  };
}

function SourceIcon({ source }: { source: string }) {
  if (source === "telegram") return <Send className="size-3.5" aria-hidden />;
  if (source === "webchat") return <MessageSquare className="size-3.5" aria-hidden />;
  return <UserPlus className="size-3.5" aria-hidden />;
}

/* ------------------------------------------------------------------ Lead drawer */
function LeadDrawer({ leadId, onClose }: { leadId: number | null; onClose: () => void }) {
  const toast = useToast();
  const { can } = useAuth();
  const invalidate = useInvalidateLeads();
  const { data: staff } = useAssignable();
  const { data: courses } = useCourses();
  const { data: branches } = useBranches();
  const { data: groups } = useGroups();
  const [tab, setTab] = useState<"profile" | "history" | "bookings">("profile");
  const [note, setNote] = useState("");
  const [bookingOpen, setBookingOpen] = useState(false);
  const [enrollOpen, setEnrollOpen] = useState(false);
  const [enrollCourse, setEnrollCourse] = useState<number | null>(null);
  const [enrollGroup, setEnrollGroup] = useState<number | null>(null);
  const [form, setForm] = useState<Partial<LeadDetail>>({});
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const query = useQuery({ queryKey: ["lead", leadId], queryFn: () => get<LeadDetail>(`/leads/${leadId}/`), enabled: !!leadId });
  const lead = query.data;
  useEffect(() => {
    if (lead) {
      setForm({ full_name: lead.full_name, phone: lead.phone, goal: lead.goal, level: lead.level, preferred_time: lead.preferred_time, language: lead.language, branch_id: lead.branch_id, interested_course_id: lead.interested_course_id });
      setEnrollCourse(lead.interested_course_id);
      setFieldErrors({});
    }
  }, [lead]);
  useEffect(() => setTab("profile"), [leadId]);

  const save = useMutation({
    mutationFn: () => patch<LeadDetail>(`/leads/${leadId}/`, form),
    onSuccess: () => { toast.success("Mijoz ma'lumotlari saqlandi"); setFieldErrors({}); invalidate(); },
    onError: (e) => {
      if (e instanceof ApiError) setFieldErrors(Object.fromEntries(Object.keys(e.fields).map((k) => [k, e.fieldError(k) ?? ""])));
      toast.error("Saqlanmadi", errorMessage(e));
    },
  });
  const status = useMutation({
    mutationFn: (s: LeadStatus) => post<LeadDetail>(`/leads/${leadId}/status/`, { status: s }),
    onSuccess: (d) => { toast.success("Holat o'zgartirildi", d.status_label); invalidate(); },
    onError: (e) => toast.error("Holat o'zgarmadi", errorMessage(e)),
  });
  const assign = useMutation({
    mutationFn: (userId: number | null) => post(`/leads/${leadId}/assign/`, { user_id: userId }),
    onSuccess: () => { toast.success("Mas'ul biriktirildi"); invalidate(); },
    onError: (e) => toast.error("Biriktirilmadi", errorMessage(e)),
  });
  const addNote = useMutation({
    mutationFn: () => post(`/leads/${leadId}/notes/`, { text: note }),
    onSuccess: () => { setNote(""); toast.success("Eslatma qo'shildi"); invalidate(); },
    onError: (e) => toast.error("Eslatma qo'shilmadi", errorMessage(e)),
  });
  const enroll = useMutation({
    mutationFn: () => post<Enrollment>(`/leads/${leadId}/enroll/`, { course_id: enrollCourse, group_id: enrollGroup }),
    onSuccess: () => { toast.success("O'qishga yozildi", "Administrator tasdig'i saqlandi."); setEnrollOpen(false); invalidate(); },
    onError: (e) => toast.error("Tasdiqlanmadi", errorMessage(e)),
  });

  const set = (k: keyof LeadDetail, v: unknown) => setForm((f) => ({ ...f, [k]: v }));

  return (
    <Drawer
      open={!!leadId}
      onClose={onClose}
      width="lg"
      title={lead?.display_name ?? "Mijoz"}
      subtitle={
        lead && (
          <span className="flex flex-wrap items-center gap-2">
            <Badge tone={leadStatusTone(lead.status)} dot>
              {lead.status_label}
            </Badge>
            <span className="inline-flex items-center gap-1">
              <SourceIcon source={lead.source} /> {lead.source_label}
            </span>
            <span>· {formatDateTime(lead.created_at)}</span>
          </span>
        )
      }
      footer={
        lead && (
          <>
            {can("manager") && lead.status !== "enrolled" && (
              <Button icon={<GraduationCap className="size-4" />} onClick={() => setEnrollOpen(true)}>
                O'qishga yozildi
              </Button>
            )}
            <Button variant="primary" icon={<CalendarPlus className="size-4" />} onClick={() => setBookingOpen(true)}>
              Sinov darsiga yozish
            </Button>
          </>
        )
      }
    >
      {query.isLoading && <Skeleton className="h-64" />}
      {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}
      {lead && (
        <>
          <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Select
              label="Holat"
              value={lead.status}
              onChange={(e) => status.mutate(e.target.value as LeadStatus)}
              options={LEAD_STATUSES.map((s) => ({ value: s.value, label: s.label, disabled: s.value === "enrolled" && !can("manager") }))}
            />
            <Select label="Mas'ul xodim" value={lead.assigned_to?.id ?? ""} onChange={(e) => assign.mutate(e.target.value ? Number(e.target.value) : null)} placeholder="Biriktirilmagan" options={(staff ?? []).map((s) => ({ value: s.user_id, label: s.full_name }))} />
          </div>
          <Tabs
            value={tab}
            onChange={setTab}
            items={[
              { value: "profile", label: "Profil" },
              { value: "history", label: "Tarix va eslatmalar", count: lead.notes.length },
              { value: "bookings", label: "Bronlar", count: lead.bookings.length },
            ]}
          />
          {tab === "profile" && (
            <form className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
              <Input label="Ism" value={form.full_name ?? ""} onChange={(e) => set("full_name", e.target.value)} error={fieldErrors.full_name} />
              <Input label="Telefon" value={form.phone ?? ""} onChange={(e) => set("phone", e.target.value)} placeholder="+998 90 123 45 67" error={fieldErrors.phone} icon={<Phone className="size-4" />} />
              <Select label="Qiziqqan kurs" value={form.interested_course_id ?? ""} onChange={(e) => set("interested_course_id", e.target.value ? Number(e.target.value) : null)} placeholder="Tanlanmagan" options={(courses ?? []).map((c) => ({ value: c.id, label: c.name }))} />
              <Select label="Filial" value={form.branch_id ?? ""} onChange={(e) => set("branch_id", e.target.value ? Number(e.target.value) : null)} placeholder="Tanlanmagan" options={(branches ?? []).map((b) => ({ value: b.id, label: b.name }))} />
              <Input label="Maqsad" value={form.goal ?? ""} onChange={(e) => set("goal", e.target.value)} />
              <Input label="Daraja" value={form.level ?? ""} onChange={(e) => set("level", e.target.value)} />
              <Input label="Qulay vaqt" value={form.preferred_time ?? ""} onChange={(e) => set("preferred_time", e.target.value)} />
              <Select label="Suhbat tili" value={form.language ?? "uz"} onChange={(e) => set("language", e.target.value)} options={LANGUAGES} />
              <div className="flex items-center justify-between gap-3 sm:col-span-2">
                <p className="text-[12px] text-ink-3">
                  Eslatmaga rozilik: <b className="text-ink">{lead.consent_reminders ? "bor" : "yo'q"}</b>
                  {lead.telegram_username && <> · Telegram: @{lead.telegram_username}</>}
                </p>
                <Button type="submit" variant="primary" loading={save.isPending}>
                  Saqlash
                </Button>
              </div>
              {lead.conversations.length > 0 && (
                <div className="sm:col-span-2">
                  <p className="mb-1.5 text-[13px] font-medium text-ink-2">Suhbatlar</p>
                  <ul className="space-y-1.5">
                    {lead.conversations.map((c) => (
                      <li key={c.id}>
                        <Link to={`/conversations/${c.id}`} className="flex items-center justify-between gap-3 rounded-lg border border-line px-3 py-2 hover:bg-surface-2">
                          <span className="min-w-0 truncate text-[13px] text-ink-2">{c.preview || "—"}</span>
                          <Badge tone={c.channel === "telegram" ? "info" : "teal"}>{c.channel === "telegram" ? "Telegram" : "Veb-chat"}</Badge>
                        </Link>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </form>
          )}
          {tab === "history" && (
            <div className="mt-4 space-y-5">
              <form onSubmit={(e) => { e.preventDefault(); if (note.trim()) addNote.mutate(); }} className="space-y-2">
                <Textarea label="Yangi eslatma" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Masalan: ertaga 10:00 da qo'ng'iroq qilish" />
                <div className="flex justify-end">
                  <Button type="submit" size="sm" variant="primary" disabled={!note.trim()} loading={addNote.isPending}>
                    Eslatma qo'shish
                  </Button>
                </div>
              </form>
              {lead.notes.length > 0 && (
                <ul className="space-y-2">
                  {lead.notes.map((n) => (
                    <li key={n.id} className="rounded-lg border border-line bg-surface-2 px-3 py-2">
                      <p className="text-sm whitespace-pre-wrap text-ink">{n.text}</p>
                      <p className="mt-1 text-[12px] text-ink-3">{n.author?.full_name ?? "—"} · {formatDateTime(n.created_at)}</p>
                    </li>
                  ))}
                </ul>
              )}
              <div>
                <p className="mb-2 text-[13px] font-medium text-ink-2">Holat o'zgarishlari tarixi</p>
                <ol className="relative space-y-3 border-l border-line pl-4">
                  {lead.status_history.map((h) => (
                    <li key={h.id} className="relative">
                      <span className="absolute top-1.5 -left-[21px] size-2.5 rounded-full border-2 border-surface bg-accent" aria-hidden />
                      <p className="text-sm text-ink">
                        {h.from_label ? `${h.from_label} → ` : ""}
                        <b>{h.to_label}</b>
                      </p>
                      <p className="text-[12px] text-ink-3">
                        {h.changed_by?.full_name ?? { ai: "AI agent", operator: "Xodim", system: "Tizim" }[h.changed_via]} · {formatDateTime(h.created_at)}
                        {h.reason && ` · ${h.reason}`}
                      </p>
                    </li>
                  ))}
                </ol>
              </div>
            </div>
          )}
          {tab === "bookings" && (
            <div className="mt-4 space-y-2">
              {lead.bookings.length === 0 && <EmptyState title="Bronlar yo'q" body="Mijozni sinov darsiga yozish uchun pastdagi tugmadan foydalaning." />}
              {lead.bookings.map((b) => (
                <Link key={b.id} to={`/bookings?booking=${b.id}`} className="flex items-center justify-between gap-3 rounded-lg border border-line px-3 py-2.5 hover:bg-surface-2">
                  <span>
                    <span className="block text-sm font-medium text-ink">{b.course_name}</span>
                    <span className="block text-[12px] text-ink-3">{b.branch_name} · {formatDateTime(b.starts_at)}</span>
                  </span>
                  <Badge tone={bookingStatusTone(b.status)} dot>
                    {b.status_label}
                  </Badge>
                </Link>
              ))}
              {lead.enrollments.length > 0 && (
                <div className="pt-3">
                  <p className="mb-1.5 text-[13px] font-medium text-ink-2">O'qishga yozilishlar</p>
                  {lead.enrollments.map((e) => (
                    <dl key={e.id} className="rounded-lg border border-line px-3">
                      <KeyValue label="Kurs">{e.course_name}</KeyValue>
                      <KeyValue label="Guruh">{e.group_name}</KeyValue>
                      <KeyValue label="Holat">{e.status_label}</KeyValue>
                      <KeyValue label="Tasdiqladi">{e.confirmed_by?.full_name}</KeyValue>
                    </dl>
                  ))}
                </div>
              )}
            </div>
          )}
          <CreateBookingDialog open={bookingOpen} onClose={() => setBookingOpen(false)} lead={lead} />
          <Dialog
            open={enrollOpen}
            onClose={() => setEnrollOpen(false)}
            title="O'qishga yozilishni tasdiqlash"
            description="Bu ko'rsatkich statistikada administrator tasdiqlagan o'quvchi sifatida hisoblanadi."
            footer={
              <>
                <Button onClick={() => setEnrollOpen(false)}>Bekor qilish</Button>
                <Button variant="primary" disabled={!enrollCourse} loading={enroll.isPending} onClick={() => enroll.mutate()}>
                  Tasdiqlash
                </Button>
              </>
            }
          >
            <div className="space-y-3">
              <Select label="Kurs" value={enrollCourse ?? ""} onChange={(e) => { setEnrollCourse(e.target.value ? Number(e.target.value) : null); setEnrollGroup(null); }} placeholder="Kursni tanlang" options={(courses ?? []).map((c) => ({ value: c.id, label: c.name }))} />
              <Select label="Guruh (ixtiyoriy)" value={enrollGroup ?? ""} onChange={(e) => setEnrollGroup(e.target.value ? Number(e.target.value) : null)} placeholder="Guruhsiz" options={(groups ?? []).filter((g) => g.course_id === enrollCourse && g.is_active).map((g) => ({ value: g.id, label: `${g.name} · ${g.branch_name}` }))} />
            </div>
          </Dialog>
        </>
      )}
    </Drawer>
  );
}

/* ------------------------------------------------------------------ New lead dialog */
function NewLeadDialog({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: (id: number) => void }) {
  const toast = useToast();
  const invalidate = useInvalidateLeads();
  const { data: courses } = useCourses(true);
  const { data: branches } = useBranches();
  const empty = { full_name: "", phone: "", source: "manual", interested_course_id: "", branch_id: "", goal: "" };
  const [form, setForm] = useState(empty);
  const [errors, setErrors] = useState<Record<string, string>>({});
  useEffect(() => {
    if (open) { setForm(empty); setErrors({}); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);
  const mutation = useMutation({
    mutationFn: () =>
      post<LeadDetail>("/leads/", {
        ...form,
        interested_course_id: form.interested_course_id ? Number(form.interested_course_id) : null,
        branch_id: form.branch_id ? Number(form.branch_id) : null,
      }),
    onSuccess: (lead) => { toast.success("Mijoz qo'shildi", lead.display_name); invalidate(); onClose(); onCreated(lead.id); },
    onError: (e) => {
      if (e instanceof ApiError) setErrors(Object.fromEntries(Object.keys(e.fields).map((k) => [k, e.fieldError(k) ?? ""])));
      toast.error("Mijoz qo'shilmadi", errorMessage(e));
    },
  });
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Yangi mijoz"
      footer={
        <>
          <Button onClick={onClose}>Bekor qilish</Button>
          <Button variant="primary" loading={mutation.isPending} onClick={() => mutation.mutate()}>
            Qo'shish
          </Button>
        </>
      }
    >
      <form className="grid grid-cols-1 gap-3 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); mutation.mutate(); }}>
        <Input label="Ism" required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} error={errors.full_name} data-autofocus />
        <Input label="Telefon" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="+998 90 123 45 67" error={errors.phone} />
        <Select label="Manba" value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} options={LEAD_SOURCES.filter((s) => !["telegram", "webchat"].includes(s.value))} error={errors.source} />
        <Select label="Qiziqqan kurs" value={form.interested_course_id} onChange={(e) => setForm({ ...form, interested_course_id: e.target.value })} placeholder="Tanlanmagan" options={(courses ?? []).map((c) => ({ value: c.id, label: c.name }))} />
        <Select label="Filial" value={form.branch_id} onChange={(e) => setForm({ ...form, branch_id: e.target.value })} placeholder="Tanlanmagan" options={(branches ?? []).map((b) => ({ value: b.id, label: b.name }))} />
        <Input label="Maqsad" value={form.goal} onChange={(e) => setForm({ ...form, goal: e.target.value })} />
        <button type="submit" className="hidden" />
      </form>
    </Dialog>
  );
}

/* ------------------------------------------------------------------ Kanban */
function Kanban({ params, onOpen }: { params: Record<string, string | number | undefined>; onOpen: (id: number) => void }) {
  const toast = useToast();
  const invalidate = useInvalidateLeads();
  const { can } = useAuth();
  const [dragId, setDragId] = useState<number | null>(null);
  const [overCol, setOverCol] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ["leads", "kanban", params],
    queryFn: () => get<{ columns: { status: LeadStatus; label: string; count: number; items: Lead[] }[] }>("/leads/kanban/", { ...params, per_column: 25 }),
    placeholderData: keepPreviousData,
  });
  const move = useMutation({
    mutationFn: ({ id, status }: { id: number; status: LeadStatus }) => post(`/leads/${id}/status/`, { status }),
    onSuccess: () => { toast.success("Holat yangilandi"); invalidate(); },
    onError: (e) => toast.error("Ko'chirilmadi", errorMessage(e)),
  });
  if (query.isLoading) return <div className="grid grid-cols-1 gap-3 md:grid-cols-3 xl:grid-cols-6">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-72" />)}</div>;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} />;
  const onDrop = (e: DragEvent, status: LeadStatus) => {
    e.preventDefault();
    setOverCol(null);
    if (dragId) move.mutate({ id: dragId, status });
    setDragId(null);
  };
  return (
    <div className="scroll-thin -mx-4 flex snap-x gap-3 overflow-x-auto px-4 pb-2 sm:mx-0 sm:px-0">
      {query.data!.columns.map((col) => (
        <section
          key={col.status}
          aria-label={`${col.label}: ${col.count}`}
          onDragOver={(e) => { e.preventDefault(); setOverCol(col.status); }}
          onDragLeave={() => setOverCol(null)}
          onDrop={(e) => onDrop(e, col.status)}
          className={cn("flex w-[272px] shrink-0 snap-start flex-col rounded-[14px] border bg-surface-2 transition-colors", overCol === col.status ? "border-accent" : "border-line")}
        >
          <header className="flex items-center justify-between px-3 py-2.5">
            <Badge tone={leadStatusTone(col.status)} dot>
              {col.label}
            </Badge>
            <span className="text-[12px] font-semibold text-ink-3 tabular">{col.count}</span>
          </header>
          <div className="scroll-thin flex max-h-[62vh] flex-col gap-2 overflow-y-auto px-2 pb-2">
            {col.items.length === 0 && <p className="px-2 py-6 text-center text-[12px] text-ink-3">Bo'sh</p>}
            {col.items.map((l) => (
              <article
                key={l.id}
                draggable
                onDragStart={() => setDragId(l.id)}
                className="group rounded-xl border border-line bg-surface p-3 shadow-card hover:border-line-strong"
              >
                <button type="button" onClick={() => onOpen(l.id)} className="block w-full text-left">
                  <p className="truncate text-sm font-medium text-ink">{l.display_name}</p>
                  <p className="mt-0.5 truncate text-[12px] text-ink-3">{l.interested_course_name || "Kurs aniqlanmagan"}</p>
                  <div className="mt-2 flex items-center justify-between gap-2 text-[12px] text-ink-3">
                    <span className="inline-flex items-center gap-1">
                      <SourceIcon source={l.source} />
                      {l.source_label}
                    </span>
                    <span>{relativeTime(l.last_activity_at)}</span>
                  </div>
                </button>
                <label className="mt-2 block">
                  <span className="sr-only">{l.display_name} holatini o'zgartirish</span>
                  <select
                    value={l.status}
                    onChange={(e) => move.mutate({ id: l.id, status: e.target.value as LeadStatus })}
                    className="h-7 w-full rounded-md border border-line bg-surface-2 px-2 text-[12px] text-ink-2"
                  >
                    {LEAD_STATUSES.map((s) => (
                      <option key={s.value} value={s.value} disabled={s.value === "enrolled" && !can("manager")}>
                        → {s.label}
                      </option>
                    ))}
                  </select>
                </label>
              </article>
            ))}
            {col.count > col.items.length && <p className="px-2 py-1 text-center text-[12px] text-ink-3">+{col.count - col.items.length} ta — jadval ko'rinishida</p>}
          </div>
        </section>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ Page */
export default function LeadsPage() {
  const [params, setParams] = useSearchParams();
  const { branchId } = useFilters();
  const { me } = useAuth();
  const { data: courses } = useCourses();
  const { data: staff } = useAssignable();
  const [view, setView] = useState<View>((me?.preferences?.leads_view as View) || "table");
  const [search, setSearch] = useState(params.get("search") ?? "");
  const [debounced, setDebounced] = useState(search);
  const [status, setStatus] = useState(params.get("status") ?? "");
  const [source, setSource] = useState("");
  const [course, setCourse] = useState("");
  const [assigned, setAssigned] = useState("");
  const [page, setPage] = useState(1);
  const [newOpen, setNewOpen] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const activeFilters = [status, source, course, assigned].filter(Boolean).length;
  const openLead = Number(params.get("lead")) || null;

  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(search), 300);
    return () => window.clearTimeout(t);
  }, [search]);
  useEffect(() => setPage(1), [debounced, status, source, course, assigned, branchId]);

  const filterParams = useMemo(
    () => ({ search: debounced || undefined, status: status || undefined, source: source || undefined, course: course || undefined, assigned_to: assigned || undefined, branch: branchId ?? undefined }),
    [debounced, status, source, course, assigned, branchId],
  );
  const list = useQuery({
    queryKey: ["leads", "list", filterParams, page],
    queryFn: () => get<Paginated<Lead>>("/leads/", { ...filterParams, page, page_size: 15 }),
    placeholderData: keepPreviousData,
    enabled: view === "table",
  });

  const setOpenLead = (id: number | null) => {
    const next = new URLSearchParams(params);
    if (id) next.set("lead", String(id));
    else next.delete("lead");
    setParams(next, { replace: true });
  };
  const changeView = (v: View) => {
    setView(v);
    patch("/auth/me/", { preferences: { leads_view: v } }).catch(() => undefined);
  };

  return (
    <>
      <PageHeader
        title="Mijozlar"
        subtitle="Barcha kanallardan kelgan murojaatlar, holatlar va mas'ul xodimlar"
        actions={
          <>
            <Segmented label="Ko'rinish" value={view} onChange={changeView} items={[{ value: "table", label: "Jadval", icon: <List className="size-3.5" /> }, { value: "kanban", label: "Kanban", icon: <KanbanSquare className="size-3.5" /> }]} />
            <Button variant="primary" icon={<Plus className="size-4" />} onClick={() => setNewOpen(true)}>
              Yangi mijoz
            </Button>
          </>
        }
      />
      <Card className="mb-4 p-3">
        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-5">
          <div className="flex gap-2">
            <div className="min-w-0 flex-1">
              <Input aria-label="Qidirish" placeholder="Ism, telefon, Telegram…" value={search} onChange={(e) => setSearch(e.target.value)} icon={<Search className="size-4" />} />
            </div>
            <Button className="sm:hidden" icon={<SlidersHorizontal className="size-4" />} onClick={() => setFiltersOpen((v) => !v)} aria-expanded={filtersOpen} aria-controls="lead-filters">
              Filtr{activeFilters ? ` (${activeFilters})` : ""}
            </Button>
          </div>
          <div id="lead-filters" className={cn("contents", !filtersOpen && "max-sm:hidden")}>
          <Select aria-label="Holat" value={status} onChange={(e) => setStatus(e.target.value)} placeholder="Barcha holatlar" options={LEAD_STATUSES} />
          <Select aria-label="Manba" value={source} onChange={(e) => setSource(e.target.value)} placeholder="Barcha manbalar" options={LEAD_SOURCES} />
          <Select aria-label="Kurs" value={course} onChange={(e) => setCourse(e.target.value)} placeholder="Barcha kurslar" options={(courses ?? []).map((c) => ({ value: c.id, label: c.name }))} />
          <Select aria-label="Mas'ul" value={assigned} onChange={(e) => setAssigned(e.target.value)} placeholder="Barcha mas'ullar" options={[{ value: "me", label: "Menga biriktirilgan" }, { value: "none", label: "Biriktirilmagan" }, ...(staff ?? []).map((s) => ({ value: s.user_id, label: s.full_name }))]} />
          </div>
        </div>
      </Card>

      {view === "kanban" ? (
        <Kanban params={filterParams} onOpen={setOpenLead} />
      ) : (
        <Card className="overflow-hidden">
          {list.isError ? (
            <ErrorState error={list.error} onRetry={() => list.refetch()} />
          ) : list.isLoading ? (
            <div className="space-y-2 p-4">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-11" />)}</div>
          ) : list.data!.results.length === 0 ? (
            <EmptyState title="Mijoz topilmadi" body="Filtrlarni o'zgartiring yoki yangi mijoz qo'shing." action={<Button variant="primary" onClick={() => setNewOpen(true)} icon={<Plus className="size-4" />}>Yangi mijoz</Button>} />
          ) : (
            <>
              {/* Desktop jadval */}
              <div className="hidden overflow-x-auto md:block">
                <table className="w-full text-sm">
                  <thead className="border-b border-line bg-surface-2 text-left text-[12px] font-medium text-ink-3">
                    <tr>
                      <th className="px-4 py-2.5 font-medium">Mijoz</th>
                      <th className="px-3 py-2.5 font-medium">Holat</th>
                      <th className="px-3 py-2.5 font-medium">Manba</th>
                      <th className="px-3 py-2.5 font-medium">Kurs</th>
                      <th className="hidden px-3 py-2.5 font-medium xl:table-cell">Filial</th>
                      <th className="px-3 py-2.5 font-medium">Mas'ul</th>
                      <th className="px-4 py-2.5 text-right font-medium">Yaratilgan</th>
                    </tr>
                  </thead>
                  <tbody>
                    {list.data!.results.map((l) => (
                      <tr key={l.id} className="cursor-pointer border-b border-line last:border-0 hover:bg-surface-2" onClick={() => setOpenLead(l.id)}>
                        <td className="px-4 py-2.5">
                          <button type="button" className="flex items-center gap-2.5 text-left" onClick={(e) => { e.stopPropagation(); setOpenLead(l.id); }}>
                            <Avatar name={l.display_name} size="sm" tone={l.source === "telegram" ? "accent" : l.source === "webchat" ? "teal" : "neutral"} />
                            <span>
                              <span className="block font-medium text-ink">{l.display_name}</span>
                              <span className="block text-[12px] text-ink-3 tabular">{formatPhone(l.phone) || (l.telegram_username ? `@${l.telegram_username}` : "—")}</span>
                            </span>
                          </button>
                        </td>
                        <td className="px-3 py-2.5"><Badge tone={leadStatusTone(l.status)} dot>{l.status_label}</Badge></td>
                        <td className="px-3 py-2.5 text-ink-2"><span className="inline-flex items-center gap-1.5"><SourceIcon source={l.source} />{l.source_label}</span></td>
                        <td className="px-3 py-2.5 text-ink-2">{l.interested_course_name || "—"}</td>
                        <td className="hidden px-3 py-2.5 text-ink-2 xl:table-cell">{l.branch_name || "—"}</td>
                        <td className="px-3 py-2.5">{l.assigned_to ? <span className="inline-flex items-center gap-2 text-ink-2"><Avatar initials={l.assigned_to.initials} name={l.assigned_to.full_name} size="sm" tone="neutral" />{l.assigned_to.full_name}</span> : <span className="text-ink-3">—</span>}</td>
                        <td className="px-4 py-2.5 text-right text-[13px] text-ink-3 tabular">{formatDateTime(l.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {/* Mobil kartalar */}
              <ul className="divide-y divide-line md:hidden">
                {list.data!.results.map((l) => (
                  <li key={l.id}>
                    <button type="button" onClick={() => setOpenLead(l.id)} className="flex w-full items-center gap-3 px-4 py-3 text-left">
                      <Avatar name={l.display_name} size="md" />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium text-ink">{l.display_name}</span>
                        <span className="block truncate text-[12px] text-ink-3">{l.interested_course_name || "—"} · {l.source_label}</span>
                      </span>
                      <Badge tone={leadStatusTone(l.status)}>{l.status_label}</Badge>
                    </button>
                  </li>
                ))}
              </ul>
              <div className="border-t border-line px-4 py-3">
                <Pagination page={list.data!.page} totalPages={list.data!.total_pages} count={list.data!.count} onChange={setPage} />
              </div>
            </>
          )}
        </Card>
      )}
      <LeadDrawer leadId={openLead} onClose={() => setOpenLead(null)} />
      <NewLeadDialog open={newOpen} onClose={() => setNewOpen(false)} onCreated={(id) => setOpenLead(id)} />
    </>
  );
}
