import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Button } from "../components/ui/Button";
import { Select, Textarea } from "../components/ui/Form";
import { Dialog } from "../components/ui/Overlay";
import { Spinner } from "../components/ui/States";
import { useToast } from "../contexts/ToastContext";
import { errorMessage, get, post } from "../lib/api";
import { formatDayKey, formatTime, todayKey, dateKey } from "../lib/format";
import { useCourses } from "../lib/queries";
import type { Booking, Lead, Paginated, TrialSlot } from "../lib/types";

export function useAvailableSlots(courseId: number | null, enabled = true) {
  return useQuery({
    queryKey: ["trial-slots", "available", courseId],
    queryFn: () => get<Paginated<TrialSlot>>("/trial-slots/", { available: 1, course: courseId ?? undefined, date_from: todayKey(), page_size: 60 }).then((r) => r.results),
    enabled: enabled && !!courseId,
  });
}

function slotLabel(s: TrialSlot) {
  return `${formatDayKey(dateKey(s.starts_at), { weekday: true })}, ${formatTime(s.starts_at)} · ${s.branch_name} · ${s.seats_left} joy`;
}

export function CreateBookingDialog({ open, onClose, lead: fixedLead, defaultCourseId }: { open: boolean; onClose: () => void; lead?: Pick<Lead, "id" | "display_name" | "interested_course_id"> | null; defaultCourseId?: number | null }) {
  const qc = useQueryClient();
  const toast = useToast();
  const { data: courses } = useCourses(true);
  const [search, setSearch] = useState("");
  const [leadId, setLeadId] = useState<number | null>(fixedLead?.id ?? null);
  const [courseId, setCourseId] = useState<number | null>(defaultCourseId ?? fixedLead?.interested_course_id ?? null);
  const [slotId, setSlotId] = useState<number | null>(null);
  const [notes, setNotes] = useState("");
  const [idemKey] = useState(() => (crypto.randomUUID ? crypto.randomUUID() : String(Date.now())));

  useEffect(() => {
    if (open) {
      setLeadId(fixedLead?.id ?? null);
      setCourseId(defaultCourseId ?? fixedLead?.interested_course_id ?? null);
      setSlotId(null);
      setNotes("");
    }
  }, [open, fixedLead, defaultCourseId]);

  const leads = useQuery({
    queryKey: ["leads", "picker", search],
    queryFn: () => get<Paginated<Lead>>("/leads/", { search, page_size: 20, ordering: "-last_activity_at" }).then((r) => r.results),
    enabled: open && !fixedLead,
  });
  const slots = useAvailableSlots(courseId, open);

  const mutation = useMutation({
    mutationFn: () => post<Booking>("/bookings/", { lead_id: leadId, slot_id: slotId, notes, idempotency_key: idemKey }),
    onSuccess: (b) => {
      toast.success("Sinov darsiga yozildi", `${b.lead_name} — ${b.course_name}, ${formatDayKey(dateKey(b.starts_at))} ${formatTime(b.starts_at)}`);
      void qc.invalidateQueries({ queryKey: ["bookings"] });
      void qc.invalidateQueries({ queryKey: ["trial-slots"] });
      void qc.invalidateQueries({ queryKey: ["leads"] });
      void qc.invalidateQueries({ queryKey: ["lead"] });
      void qc.invalidateQueries({ queryKey: ["analytics"] });
      onClose();
    },
    onError: (e) => toast.error("Bron yaratilmadi", errorMessage(e)),
  });

  const leadOptions = useMemo(() => (leads.data ?? []).map((l) => ({ value: l.id, label: `${l.display_name}${l.phone ? ` · ${l.phone}` : ""}` })), [leads.data]);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Sinov darsiga yozish"
      description="Bo'sh joy server tomonida tekshiriladi; oxirgi joyni ikki kishi bir vaqtda ololmaydi."
      footer={
        <>
          <Button onClick={onClose}>Bekor qilish</Button>
          <Button variant="primary" disabled={!leadId || !slotId} loading={mutation.isPending} onClick={() => mutation.mutate()}>
            Bronni tasdiqlash
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {fixedLead ? (
          <p className="rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm">
            Mijoz: <span className="font-semibold text-ink">{fixedLead.display_name}</span>
          </p>
        ) : (
          <div className="space-y-2">
            <label className="text-[13px] font-medium text-ink-2" htmlFor="lead-search">
              Mijoz
            </label>
            <input id="lead-search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Ism yoki telefon bilan qidiring" className="h-9 w-full rounded-[10px] border border-line bg-surface px-3 text-sm text-ink" />
            <Select aria-label="Mijozni tanlang" value={leadId ?? ""} onChange={(e) => setLeadId(e.target.value ? Number(e.target.value) : null)} placeholder={leads.isLoading ? "Yuklanmoqda…" : "Mijozni tanlang"} options={leadOptions} />
          </div>
        )}
        <Select label="Kurs" value={courseId ?? ""} onChange={(e) => { setCourseId(e.target.value ? Number(e.target.value) : null); setSlotId(null); }} placeholder="Kursni tanlang" options={(courses ?? []).map((c) => ({ value: c.id, label: c.name }))} />
        <div>
          <Select
            label="Bo'sh sinov darsi"
            value={slotId ?? ""}
            onChange={(e) => setSlotId(e.target.value ? Number(e.target.value) : null)}
            placeholder={!courseId ? "Avval kursni tanlang" : slots.isLoading ? "Yuklanmoqda…" : slots.data?.length ? "Vaqtni tanlang" : "Bo'sh vaqt yo'q"}
            options={(slots.data ?? []).map((s) => ({ value: s.id, label: slotLabel(s) }))}
            disabled={!courseId}
          />
          {slots.isFetching && <Spinner className="mt-1" />}
        </div>
        <Textarea label="Izoh (ixtiyoriy)" value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={255} />
      </div>
    </Dialog>
  );
}

export function RescheduleDialog({ booking, onClose }: { booking: Booking | null; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [slotId, setSlotId] = useState<number | null>(null);
  const slots = useAvailableSlots(booking?.course_id ?? null, !!booking);
  useEffect(() => setSlotId(null), [booking]);
  const mutation = useMutation({
    mutationFn: () => post<Booking>(`/bookings/${booking!.id}/reschedule/`, { slot_id: slotId }),
    onSuccess: (b) => {
      toast.success("Bron ko'chirildi", `${formatDayKey(dateKey(b.starts_at))}, ${formatTime(b.starts_at)}`);
      void qc.invalidateQueries({ queryKey: ["bookings"] });
      void qc.invalidateQueries({ queryKey: ["booking", b.id] });
      void qc.invalidateQueries({ queryKey: ["trial-slots"] });
      onClose();
    },
    onError: (e) => toast.error("Ko'chirib bo'lmadi", errorMessage(e) + " Eski bron o'zgarmadi."),
  });
  return (
    <Dialog
      open={!!booking}
      onClose={onClose}
      title="Bronni ko'chirish"
      description="Yangi joy olinmasa, eski bron saqlanib qoladi (atomar amal)."
      footer={
        <>
          <Button onClick={onClose}>Bekor qilish</Button>
          <Button variant="primary" disabled={!slotId} loading={mutation.isPending} onClick={() => mutation.mutate()}>
            Ko'chirish
          </Button>
        </>
      }
    >
      {booking && (
        <div className="space-y-3">
          <p className="text-sm text-ink-2">
            Joriy vaqt: <span className="font-semibold text-ink">{formatDayKey(dateKey(booking.starts_at), { weekday: true })}, {formatTime(booking.starts_at)}</span> · {booking.branch_name}
          </p>
          <Select
            label="Yangi vaqt"
            value={slotId ?? ""}
            onChange={(e) => setSlotId(e.target.value ? Number(e.target.value) : null)}
            placeholder={slots.isLoading ? "Yuklanmoqda…" : "Vaqtni tanlang"}
            options={(slots.data ?? []).filter((s) => s.id !== booking.slot_id).map((s) => ({ value: s.id, label: slotLabel(s) }))}
          />
        </div>
      )}
    </Dialog>
  );
}
