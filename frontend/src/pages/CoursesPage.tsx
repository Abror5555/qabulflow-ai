import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarPlus, Pencil, Plus, Sparkles, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, PageHeader } from "../components/ui/Card";
import { Checkbox, Input, Select, Switch, Textarea } from "../components/ui/Form";
import { ConfirmDialog, Dialog, Drawer } from "../components/ui/Overlay";
import { Pagination, Tabs } from "../components/ui/Misc";
import { EmptyState, ErrorState, Skeleton } from "../components/ui/States";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { ApiError, del, errorMessage, get, patch, post } from "../lib/api";
import { dateKey, formatDayKey, formatMoney, formatTime, todayKey, toLocalInputValue, WEEKDAYS_SHORT } from "../lib/format";
import { useBranches, useCourses, useGroups } from "../lib/queries";
import type { Course, Group, Paginated, TrialSlot } from "../lib/types";

type Tab = "courses" | "groups" | "slots";

function useFieldErrors() {
  const [errors, setErrors] = useState<Record<string, string>>({});
  const capture = (e: unknown) => {
    if (e instanceof ApiError) setErrors(Object.fromEntries(Object.keys(e.fields).map((k) => [k, e.fieldError(k) ?? ""])));
  };
  return { errors, setErrors, capture };
}

const LEVELS = [
  { value: "beginner", label: "Boshlang'ich" },
  { value: "intermediate", label: "O'rta" },
  { value: "advanced", label: "Yuqori" },
  { value: "all", label: "Barcha darajalar" },
];

/* ------------------------------------------------------------------ Course form */
function CourseDrawer({ course, open, onClose }: { course: Course | null; open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const { errors, setErrors, capture } = useFieldErrors();
  const blank = { name: "", description: "", level: "beginner", teaching_language: "O'zbek", price: "", price_period: "month", duration_months: 3, lessons_per_week: 3, lesson_minutes: 90, keywords: "", is_active: true };
  const [form, setForm] = useState(blank);
  useEffect(() => {
    if (!open) return;
    setErrors({});
    setForm(course ? { ...course, price: String(Number(course.price)), keywords: course.keywords.join(", ") } : blank);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, course]);
  const mutation = useMutation({
    mutationFn: () => {
      const body = { ...form, keywords: form.keywords.split(",").map((k) => k.trim()).filter(Boolean), price: form.price || "0" };
      return course ? patch<Course>(`/courses/${course.id}/`, body) : post<Course>("/courses/", body);
    },
    onSuccess: (c) => {
      toast.success(course ? "Kurs yangilandi" : "Kurs qo'shildi", c.name);
      void qc.invalidateQueries({ queryKey: ["courses"] });
      onClose();
    },
    onError: (e) => { capture(e); toast.error("Saqlanmadi", errorMessage(e)); },
  });
  const set = (k: string, v: unknown) => setForm((f) => ({ ...f, [k]: v }));
  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={course ? "Kursni tahrirlash" : "Yangi kurs"}
      footer={
        <>
          <Button onClick={onClose}>Bekor qilish</Button>
          <Button variant="primary" loading={mutation.isPending} onClick={() => mutation.mutate()}>
            Saqlash
          </Button>
        </>
      }
    >
      <form className="grid grid-cols-1 gap-3 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); mutation.mutate(); }}>
        <Input className="sm:col-span-2" label="Nomi" required value={form.name} onChange={(e) => set("name", e.target.value)} error={errors.name} data-autofocus />
        <div className="sm:col-span-2">
          <Textarea label="Tavsif" value={form.description} onChange={(e) => set("description", e.target.value)} hint="AI mijozga kurs haqida shu matndan foydalanadi" />
        </div>
        <Input label="Narx (so'm)" type="number" min={0} required value={form.price} onChange={(e) => set("price", e.target.value)} error={errors.price} />
        <Select label="Narx davri" value={form.price_period} onChange={(e) => set("price_period", e.target.value)} options={[{ value: "month", label: "Oyiga" }, { value: "course", label: "Butun kurs uchun" }]} />
        <Select label="Daraja" value={form.level} onChange={(e) => set("level", e.target.value)} options={LEVELS} />
        <Input label="O'qitish tili" value={form.teaching_language} onChange={(e) => set("teaching_language", e.target.value)} />
        <Input label="Davomiyligi (oy)" type="number" min={1} value={form.duration_months} onChange={(e) => set("duration_months", Number(e.target.value))} />
        <Input label="Haftasiga darslar" type="number" min={1} value={form.lessons_per_week} onChange={(e) => set("lessons_per_week", Number(e.target.value))} />
        <Input label="Dars davomiyligi (daqiqa)" type="number" min={15} value={form.lesson_minutes} onChange={(e) => set("lesson_minutes", Number(e.target.value))} />
        <Input label="Kalit so'zlar" value={form.keywords} onChange={(e) => set("keywords", e.target.value)} hint="Vergul bilan: ielts, айелтс" error={errors.keywords} />
        <div className="sm:col-span-2">
          <Switch checked={form.is_active} onChange={(v) => set("is_active", v)} label="Faol kurs" description="Nofaol kurs AI tomonidan taklif qilinmaydi va unga bron yaratilmaydi" />
        </div>
        <button type="submit" className="hidden" />
      </form>
    </Drawer>
  );
}

/* ------------------------------------------------------------------ Group form */
function GroupDrawer({ group, open, onClose }: { group: Group | null; open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const { data: courses } = useCourses();
  const { data: branches } = useBranches();
  const { errors, setErrors, capture } = useFieldErrors();
  const blank = { name: "", course_id: "", branch_id: "", teacher_name: "", days: [0, 2, 4] as number[], start_time: "10:00", end_time: "11:30", capacity: 12, start_date: "", is_active: true };
  const [form, setForm] = useState(blank);
  useEffect(() => {
    if (!open) return;
    setErrors({});
    setForm(group ? { ...group, course_id: String(group.course_id), branch_id: String(group.branch_id), start_time: group.start_time.slice(0, 5), end_time: group.end_time.slice(0, 5), start_date: group.start_date ?? "" } : blank);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, group]);
  const mutation = useMutation({
    mutationFn: () => {
      const body = { ...form, course_id: Number(form.course_id) || null, branch_id: Number(form.branch_id) || null, start_date: form.start_date || null };
      return group ? patch<Group>(`/groups/${group.id}/`, body) : post<Group>("/groups/", body);
    },
    onSuccess: (g) => {
      toast.success(group ? "Guruh yangilandi" : "Guruh qo'shildi", g.name);
      void qc.invalidateQueries({ queryKey: ["groups"] });
      void qc.invalidateQueries({ queryKey: ["courses"] });
      onClose();
    },
    onError: (e) => { capture(e); toast.error("Saqlanmadi", errorMessage(e)); },
  });
  const set = (k: string, v: unknown) => setForm((f) => ({ ...f, [k]: v }));
  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={group ? "Guruhni tahrirlash" : "Yangi guruh"}
      footer={
        <>
          <Button onClick={onClose}>Bekor qilish</Button>
          <Button variant="primary" loading={mutation.isPending} onClick={() => mutation.mutate()}>
            Saqlash
          </Button>
        </>
      }
    >
      <form className="grid grid-cols-1 gap-3 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); mutation.mutate(); }}>
        <Input className="sm:col-span-2" label="Guruh nomi" required value={form.name} onChange={(e) => set("name", e.target.value)} error={errors.name} data-autofocus />
        <Select label="Kurs" required value={form.course_id} onChange={(e) => set("course_id", e.target.value)} placeholder="Tanlang" options={(courses ?? []).map((c) => ({ value: c.id, label: c.name }))} error={errors.course_id} />
        <Select label="Filial" required value={form.branch_id} onChange={(e) => set("branch_id", e.target.value)} placeholder="Tanlang" options={(branches ?? []).map((b) => ({ value: b.id, label: b.name }))} error={errors.branch_id} />
        <Input label="O'qituvchi (ichki)" value={form.teacher_name} onChange={(e) => set("teacher_name", e.target.value)} hint="Mijozlarga ko'rsatilmaydi" />
        <Input label="Sig'im (o'quvchi)" type="number" min={1} value={form.capacity} onChange={(e) => set("capacity", Number(e.target.value))} error={errors.capacity} />
        <fieldset className="sm:col-span-2">
          <legend className="mb-1.5 text-[13px] font-medium text-ink-2">Dars kunlari</legend>
          <div className="flex flex-wrap gap-3">
            {WEEKDAYS_SHORT.map((w, i) => (
              <Checkbox key={w} label={w} checked={form.days.includes(i)} onChange={(v) => set("days", v ? [...form.days, i].sort() : form.days.filter((d) => d !== i))} />
            ))}
          </div>
          {errors.days && <p className="mt-1 text-[12px] text-danger-strong">{errors.days}</p>}
        </fieldset>
        <Input label="Boshlanish" type="time" value={form.start_time} onChange={(e) => set("start_time", e.target.value)} />
        <Input label="Tugash" type="time" value={form.end_time} onChange={(e) => set("end_time", e.target.value)} error={errors.end_time} />
        <Input label="Guruh boshlangan sana" type="date" value={form.start_date} onChange={(e) => set("start_date", e.target.value)} />
        <div className="flex items-end sm:col-span-1">
          <Switch checked={form.is_active} onChange={(v) => set("is_active", v)} label="Faol guruh" />
        </div>
        <button type="submit" className="hidden" />
      </form>
    </Drawer>
  );
}

/* ------------------------------------------------------------------ Slot dialogs */
function SlotDialog({ open, onClose, slot }: { open: boolean; onClose: () => void; slot: TrialSlot | null }) {
  const qc = useQueryClient();
  const toast = useToast();
  const { data: groups } = useGroups();
  const { errors, setErrors, capture } = useFieldErrors();
  const [form, setForm] = useState({ group_id: "", starts_at: "", capacity: 4, notes: "", status: "open" });
  useEffect(() => {
    if (!open) return;
    setErrors({});
    setForm(slot ? { group_id: String(slot.group_id), starts_at: toLocalInputValue(slot.starts_at), capacity: slot.capacity, notes: slot.notes, status: slot.status } : { group_id: "", starts_at: `${todayKey()}T18:00`, capacity: 4, notes: "", status: "open" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, slot]);
  const mutation = useMutation({
    mutationFn: () => {
      if (slot) {
        const body: Record<string, unknown> = { capacity: form.capacity, notes: form.notes, status: form.status };
        if (toLocalInputValue(slot.starts_at) !== form.starts_at) body.starts_at = form.starts_at;
        return patch<TrialSlot>(`/trial-slots/${slot.id}/`, body);
      }
      return post<TrialSlot>("/trial-slots/", { group_id: Number(form.group_id) || null, starts_at: form.starts_at, capacity: form.capacity, notes: form.notes });
    },
    onSuccess: () => {
      toast.success(slot ? "Sinov darsi yangilandi" : "Sinov darsi qo'shildi");
      void qc.invalidateQueries({ queryKey: ["trial-slots"] });
      onClose();
    },
    onError: (e) => { capture(e); toast.error("Saqlanmadi", errorMessage(e)); },
  });
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={slot ? "Sinov darsini tahrirlash" : "Sinov darsi qo'shish"}
      description="Vaqt tashkilot vaqt zonasida kiritiladi."
      footer={
        <>
          <Button onClick={onClose}>Bekor qilish</Button>
          <Button variant="primary" loading={mutation.isPending} onClick={() => mutation.mutate()}>
            Saqlash
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Select className="sm:col-span-2" label="Guruh" value={form.group_id} disabled={!!slot} onChange={(e) => setForm({ ...form, group_id: e.target.value })} placeholder="Tanlang" options={(groups ?? []).filter((g) => g.is_active || String(g.id) === form.group_id).map((g) => ({ value: g.id, label: `${g.name} · ${g.course_name} · ${g.branch_name}` }))} error={errors.group_id} />
        <Input label="Boshlanish vaqti" type="datetime-local" value={form.starts_at} onChange={(e) => setForm({ ...form, starts_at: e.target.value })} error={errors.starts_at} />
        <Input label="Joylar soni" type="number" min={1} value={form.capacity} onChange={(e) => setForm({ ...form, capacity: Number(e.target.value) })} error={errors.capacity} />
        {slot && <Select label="Holat" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} options={[{ value: "open", label: "Ochiq" }, { value: "cancelled", label: "Bekor qilingan" }]} error={errors.status} />}
        <Input className="sm:col-span-2" label="Izoh" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
      </div>
    </Dialog>
  );
}

function GenerateDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const { data: groups } = useGroups();
  const [groupId, setGroupId] = useState("");
  const [weeks, setWeeks] = useState(2);
  const [capacity, setCapacity] = useState(4);
  const mutation = useMutation({
    mutationFn: () => post<TrialSlot[]>("/trial-slots/generate/", { group_id: Number(groupId), weeks, capacity }),
    onSuccess: (list) => {
      toast.success("Sinov darslari yaratildi", `${list.length} ta yangi slot (takrorlar o'tkazib yuborildi)`);
      void qc.invalidateQueries({ queryKey: ["trial-slots"] });
      onClose();
    },
    onError: (e) => toast.error("Yaratilmadi", errorMessage(e)),
  });
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Jadval asosida sinov darslari"
      description="Guruh dars kunlari va vaqti bo'yicha keyingi haftalar uchun slotlar yaratiladi."
      footer={
        <>
          <Button onClick={onClose}>Bekor qilish</Button>
          <Button variant="primary" disabled={!groupId} loading={mutation.isPending} onClick={() => mutation.mutate()}>
            Yaratish
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Select className="sm:col-span-2" label="Guruh" value={groupId} onChange={(e) => setGroupId(e.target.value)} placeholder="Tanlang" options={(groups ?? []).filter((g) => g.is_active).map((g) => ({ value: g.id, label: `${g.name} · ${g.schedule_label}` }))} />
        <Input label="Necha hafta" type="number" min={1} max={8} value={weeks} onChange={(e) => setWeeks(Number(e.target.value))} />
        <Input label="Har bir slotda joy" type="number" min={1} max={50} value={capacity} onChange={(e) => setCapacity(Number(e.target.value))} />
      </div>
    </Dialog>
  );
}

/* ------------------------------------------------------------------ Page */
export default function CoursesPage() {
  const { can } = useAuth();
  const toast = useToast();
  const qc = useQueryClient();
  const editable = can("manager");
  const [tab, setTab] = useState<Tab>("courses");
  const courses = useCourses();
  const groups = useGroups();
  const [courseEdit, setCourseEdit] = useState<{ open: boolean; item: Course | null }>({ open: false, item: null });
  const [groupEdit, setGroupEdit] = useState<{ open: boolean; item: Group | null }>({ open: false, item: null });
  const [slotEdit, setSlotEdit] = useState<{ open: boolean; item: TrialSlot | null }>({ open: false, item: null });
  const [generateOpen, setGenerateOpen] = useState(false);
  const [toDelete, setToDelete] = useState<{ kind: "courses" | "groups" | "trial-slots"; id: number; name: string } | null>(null);
  const [slotPage, setSlotPage] = useState(1);
  const [slotCourse, setSlotCourse] = useState("");

  const slots = useQuery({
    queryKey: ["trial-slots", "list", slotPage, slotCourse],
    queryFn: () => get<Paginated<TrialSlot>>("/trial-slots/", { date_from: todayKey(), page: slotPage, page_size: 15, course: slotCourse || undefined }),
    enabled: tab === "slots",
    placeholderData: keepPreviousData,
  });

  const remove = useMutation({
    mutationFn: () => del(`/${toDelete!.kind}/${toDelete!.id}/`),
    onSuccess: () => {
      toast.success("O'chirildi", toDelete?.name);
      void qc.invalidateQueries({ queryKey: [toDelete!.kind === "trial-slots" ? "trial-slots" : toDelete!.kind] });
      setToDelete(null);
    },
    onError: (e) => { toast.error("O'chirib bo'lmadi", errorMessage(e)); setToDelete(null); },
  });
  const toggleActive = useMutation({
    mutationFn: ({ kind, id, active }: { kind: "courses" | "groups"; id: number; active: boolean }) => patch(`/${kind}/${id}/`, { is_active: active }),
    onSuccess: (_, v) => { toast.success(v.active ? "Faollashtirildi" : "Nofaol qilindi"); void qc.invalidateQueries({ queryKey: [v.kind] }); },
    onError: (e) => toast.error("Bajarilmadi", errorMessage(e)),
  });

  const addAction =
    tab === "courses" ? (
      <Button variant="primary" icon={<Plus className="size-4" />} onClick={() => setCourseEdit({ open: true, item: null })}>Kurs qo'shish</Button>
    ) : tab === "groups" ? (
      <Button variant="primary" icon={<Plus className="size-4" />} onClick={() => setGroupEdit({ open: true, item: null })}>Guruh qo'shish</Button>
    ) : (
      <>
        <Button icon={<Sparkles className="size-4" />} onClick={() => setGenerateOpen(true)}>Jadvaldan yaratish</Button>
        <Button variant="primary" icon={<CalendarPlus className="size-4" />} onClick={() => setSlotEdit({ open: true, item: null })}>Slot qo'shish</Button>
      </>
    );

  return (
    <>
      <PageHeader title="Kurslar va guruhlar" subtitle="AI va operatorlar faqat shu yerdagi tasdiqlangan narx, jadval va sig'imdan foydalanadi" actions={editable ? addAction : undefined} />
      <Card>
        <div className="px-4 pt-1">
          <Tabs value={tab} onChange={setTab} items={[{ value: "courses", label: "Kurslar", count: courses.data?.length }, { value: "groups", label: "Guruhlar", count: groups.data?.length }, { value: "slots", label: "Sinov darsi slotlari" }]} />
        </div>
        <div className="p-4">
          {tab === "courses" &&
            (courses.isError ? <ErrorState error={courses.error} onRetry={() => courses.refetch()} /> : courses.isLoading ? <Skeleton className="h-64" /> : courses.data!.length === 0 ? (
              <EmptyState title="Kurslar yo'q" body="Birinchi kursni qo'shing — AI faqat shu ma'lumotlardan foydalanadi." />
            ) : (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                {courses.data!.map((c) => (
                  <article key={c.id} className="flex flex-col rounded-xl border border-line p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h3 className="truncate font-semibold text-ink">{c.name}</h3>
                        <p className="text-[12px] text-ink-3">{c.level_label} · {c.teaching_language}</p>
                      </div>
                      <Badge tone={c.is_active ? "success" : "neutral"} dot>{c.is_active ? "Faol" : "Nofaol"}</Badge>
                    </div>
                    <p className="mt-2 line-clamp-2 text-[13px] text-ink-2">{c.description || "Tavsif kiritilmagan"}</p>
                    <p className="mt-3 text-lg font-semibold text-ink">
                      {formatMoney(c.price, c.currency)} <span className="text-[13px] font-normal text-ink-3">{c.price_period === "month" ? "/ oy" : "/ kurs"}</span>
                    </p>
                    <p className="mt-1 text-[12px] text-ink-3">{c.duration_months} oy · haftasiga {c.lessons_per_week} dars · {c.lesson_minutes} daq · {c.groups_count ?? 0} guruh · {c.upcoming_slots ?? 0} kelgusi slot</p>
                    {editable && (
                      <div className="mt-3 flex flex-wrap gap-2 border-t border-line pt-3">
                        <Button size="sm" icon={<Pencil className="size-3.5" />} onClick={() => setCourseEdit({ open: true, item: c })}>Tahrirlash</Button>
                        <Button size="sm" variant="ghost" onClick={() => toggleActive.mutate({ kind: "courses", id: c.id, active: !c.is_active })}>{c.is_active ? "Nofaol qilish" : "Faollashtirish"}</Button>
                        <Button size="sm" variant="dangerGhost" className="ml-auto" icon={<Trash2 className="size-3.5" />} onClick={() => setToDelete({ kind: "courses", id: c.id, name: c.name })} aria-label={`${c.name} kursini o'chirish`} />
                      </div>
                    )}
                  </article>
                ))}
              </div>
            ))}
          {tab === "groups" &&
            (groups.isError ? <ErrorState error={groups.error} onRetry={() => groups.refetch()} /> : groups.isLoading ? <Skeleton className="h-64" /> : groups.data!.length === 0 ? (
              <EmptyState title="Guruhlar yo'q" />
            ) : (
              <div className="overflow-x-auto rounded-xl border border-line">
                <table className="w-full min-w-[760px] text-sm">
                  <thead className="bg-surface-2 text-left text-[12px] text-ink-3">
                    <tr>
                      <th className="px-4 py-2.5 font-medium">Guruh</th>
                      <th className="px-3 py-2.5 font-medium">Kurs</th>
                      <th className="px-3 py-2.5 font-medium">Filial</th>
                      <th className="px-3 py-2.5 font-medium">Jadval</th>
                      <th className="px-3 py-2.5 font-medium">O'qituvchi</th>
                      <th className="px-3 py-2.5 font-medium">Sig'im</th>
                      <th className="px-3 py-2.5 font-medium">Holat</th>
                      {editable && <th className="px-4 py-2.5 text-right font-medium">Amallar</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {groups.data!.map((g) => (
                      <tr key={g.id} className="border-t border-line">
                        <td className="px-4 py-2.5 font-medium text-ink">{g.name}</td>
                        <td className="px-3 py-2.5 text-ink-2">{g.course_name}</td>
                        <td className="px-3 py-2.5 text-ink-2">{g.branch_name}</td>
                        <td className="px-3 py-2.5 text-ink-2 tabular">{g.schedule_label}</td>
                        <td className="px-3 py-2.5 text-ink-2">{g.teacher_name || "—"}</td>
                        <td className="px-3 py-2.5 text-ink-2 tabular">{g.enrolled_count}/{g.capacity}</td>
                        <td className="px-3 py-2.5"><Badge tone={g.is_active ? "success" : "neutral"} dot>{g.is_active ? "Faol" : "Nofaol"}</Badge></td>
                        {editable && (
                          <td className="px-4 py-2.5">
                            <div className="flex justify-end gap-1">
                              <Button size="icon-sm" variant="ghost" onClick={() => setGroupEdit({ open: true, item: g })} aria-label={`${g.name} guruhini tahrirlash`}><Pencil className="size-3.5" /></Button>
                              <Button size="icon-sm" variant="dangerGhost" onClick={() => setToDelete({ kind: "groups", id: g.id, name: g.name })} aria-label={`${g.name} guruhini o'chirish`}><Trash2 className="size-3.5" /></Button>
                            </div>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          {tab === "slots" && (
            <>
              <div className="mb-3 max-w-xs">
                <Select aria-label="Kurs" value={slotCourse} onChange={(e) => { setSlotCourse(e.target.value); setSlotPage(1); }} placeholder="Barcha kurslar" options={(courses.data ?? []).map((c) => ({ value: c.id, label: c.name }))} />
              </div>
              {slots.isError ? <ErrorState error={slots.error} onRetry={() => slots.refetch()} /> : slots.isLoading ? <Skeleton className="h-64" /> : slots.data!.results.length === 0 ? (
                <EmptyState title="Kelgusi sinov darslari yo'q" body="«Jadvaldan yaratish» orqali guruh jadvali asosida slotlar qo'shing." />
              ) : (
                <>
                  <div className="overflow-x-auto rounded-xl border border-line">
                    <table className="w-full min-w-[720px] text-sm">
                      <thead className="bg-surface-2 text-left text-[12px] text-ink-3">
                        <tr>
                          <th className="px-4 py-2.5 font-medium">Vaqt</th>
                          <th className="px-3 py-2.5 font-medium">Kurs</th>
                          <th className="px-3 py-2.5 font-medium">Guruh / filial</th>
                          <th className="px-3 py-2.5 font-medium">Joylar</th>
                          <th className="px-3 py-2.5 font-medium">Holat</th>
                          {editable && <th className="px-4 py-2.5 text-right font-medium">Amallar</th>}
                        </tr>
                      </thead>
                      <tbody>
                        {slots.data!.results.map((s) => (
                          <tr key={s.id} className="border-t border-line">
                            <td className="px-4 py-2.5 font-medium whitespace-nowrap text-ink tabular">{formatDayKey(dateKey(s.starts_at), { weekday: true })}, {formatTime(s.starts_at)}</td>
                            <td className="px-3 py-2.5 text-ink-2">{s.course_name}</td>
                            <td className="px-3 py-2.5 text-ink-2">{s.group_name} · {s.branch_name}</td>
                            <td className="px-3 py-2.5 tabular">
                              <span className={s.seats_left === 0 ? "font-semibold text-warning" : "text-ink-2"}>{s.seats_taken}/{s.capacity}</span>
                            </td>
                            <td className="px-3 py-2.5"><Badge tone={s.status === "open" ? (s.seats_left ? "accent" : "warning") : "neutral"}>{s.status === "cancelled" ? "Bekor qilingan" : s.seats_left ? "Ochiq" : "To'lgan"}</Badge></td>
                            {editable && (
                              <td className="px-4 py-2.5">
                                <div className="flex justify-end gap-1">
                                  <Button size="icon-sm" variant="ghost" onClick={() => setSlotEdit({ open: true, item: s })} aria-label="Slotni tahrirlash"><Pencil className="size-3.5" /></Button>
                                  <Button size="icon-sm" variant="dangerGhost" onClick={() => setToDelete({ kind: "trial-slots", id: s.id, name: `${s.course_name} ${formatTime(s.starts_at)}` })} aria-label="Slotni o'chirish"><Trash2 className="size-3.5" /></Button>
                                </div>
                              </td>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="mt-3">
                    <Pagination page={slots.data!.page} totalPages={slots.data!.total_pages} count={slots.data!.count} onChange={setSlotPage} />
                  </div>
                </>
              )}
            </>
          )}
        </div>
      </Card>
      <CourseDrawer open={courseEdit.open} course={courseEdit.item} onClose={() => setCourseEdit({ open: false, item: null })} />
      <GroupDrawer open={groupEdit.open} group={groupEdit.item} onClose={() => setGroupEdit({ open: false, item: null })} />
      <SlotDialog open={slotEdit.open} slot={slotEdit.item} onClose={() => setSlotEdit({ open: false, item: null })} />
      <GenerateDialog open={generateOpen} onClose={() => setGenerateOpen(false)} />
      <ConfirmDialog
        open={!!toDelete}
        onClose={() => setToDelete(null)}
        onConfirm={() => remove.mutate()}
        loading={remove.isPending}
        danger
        title="O'chirishni tasdiqlang"
        body={<>«{toDelete?.name}» o'chiriladi. Unga bog'liq yozuvlar bo'lsa, tizim o'chirishga ruxsat bermaydi — o'rniga nofaol qiling.</>}
        confirmLabel="O'chirish"
      />
    </>
  );
}
