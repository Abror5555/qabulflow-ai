import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, FlaskConical, RotateCcw, Send, ShieldCheck, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, CardHeader, PageHeader } from "../components/ui/Card";
import { Checkbox, Input, Select, Switch, Textarea } from "../components/ui/Form";
import { Tabs } from "../components/ui/Misc";
import { ErrorState, Skeleton } from "../components/ui/States";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { ApiError, del, errorMessage, get, post, put } from "../lib/api";
import { cn } from "../lib/cn";
import { formatTime, WEEKDAYS_SHORT } from "../lib/format";
import type { AISettings, Message } from "../lib/types";

const SAFETY_RULES = [
  "Narx, chegirma, jadval va bo'sh joy faqat bazadan olinadi — AI ularni uydirmaydi.",
  "Bron va bekor qilish faqat mijozning aniq tasdig'idan keyin, egalik tekshiruvi bilan bajariladi.",
  "Tool muvaffaqiyatli qaytmasa, \"yozildingiz\" degan javob server tomonida bloklanadi.",
  "Ichki hujjatlar, o'qituvchi va boshqa mijozlar ma'lumoti mijoz suhbatiga chiqmaydi.",
  "Hujjat ichidagi buyruqlar tizim ko'rsatmasi sifatida bajarilmaydi.",
  "Operator suhbatni olganda AI avtomatik javob bermaydi.",
];

function TagInput({ value, onChange, label }: { value: string[]; onChange: (v: string[]) => void; label: string }) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const v = draft.trim().toLowerCase();
    if (v && !value.includes(v)) onChange([...value, v]);
    setDraft("");
  };
  return (
    <div>
      <label className="text-[13px] font-medium text-ink-2" htmlFor="tag-input">
        {label}
      </label>
      <div className="mt-1.5 flex flex-wrap gap-1.5 rounded-[10px] border border-line bg-surface p-2">
        {value.map((t) => (
          <span key={t} className="inline-flex items-center gap-1 rounded-md bg-surface-3 px-2 py-0.5 text-[12px] text-ink">
            {t}
            <button type="button" onClick={() => onChange(value.filter((x) => x !== t))} aria-label={`${t} ni olib tashlash`} className="text-ink-3 hover:text-ink">
              <X className="size-3" />
            </button>
          </span>
        ))}
        <input
          id="tag-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") {
              e.preventDefault();
              add();
            }
          }}
          onBlur={add}
          placeholder="Qo'shish uchun yozing va Enter"
          className="min-w-[140px] flex-1 bg-transparent px-1 text-[13px] text-ink outline-none placeholder:text-ink-3"
        />
      </div>
    </div>
  );
}

function TestChat() {
  const qc = useQueryClient();
  const toast = useToast();
  const [text, setText] = useState("");
  const [lang, setLang] = useState("uz");
  const scrollRef = useRef<HTMLDivElement>(null);
  const query = useQuery({ queryKey: ["ai", "test-chat"], queryFn: () => get<{ conversation_id: number; language: string; messages: Message[] }>("/ai/test-chat/") });
  const send = useMutation({
    mutationFn: (t: string) => post("/ai/test-chat/", { text: t, language: lang }),
    onSuccess: () => { setText(""); void qc.invalidateQueries({ queryKey: ["ai", "test-chat"] }); },
    onError: (e) => toast.error("Javob olinmadi", errorMessage(e)),
  });
  const reset = useMutation({ mutationFn: () => del("/ai/test-chat/"), onSuccess: () => void qc.invalidateQueries({ queryKey: ["ai", "test-chat"] }) });
  const messages = query.data?.messages ?? [];
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length]);
  const samples = ["IELTS kursi narxi qancha?", "Sinov darsiga yozilmoqchiman", "Filiallaringiz qayerda?", "Oilaviy chegirma bormi?"];
  return (
    <Card className="flex h-[640px] flex-col">
      <CardHeader
        title="Test-chat"
        subtitle="Haqiqiy bron yaratilmaydi va statistikaga kirmaydi"
        icon={<FlaskConical className="size-4" />}
        actions={
          <>
            <Select aria-label="Test tili" className="h-8 w-[120px] text-[13px]" value={lang} onChange={(e) => setLang(e.target.value)} options={[{ value: "uz", label: "O'zbekcha" }, { value: "ru", label: "Русский" }, { value: "en", label: "English" }]} />
            <Button size="sm" variant="ghost" icon={<RotateCcw className="size-3.5" />} onClick={() => reset.mutate()} loading={reset.isPending}>
              Tozalash
            </Button>
          </>
        }
      />
      <div ref={scrollRef} className="scroll-thin min-h-0 flex-1 space-y-2.5 overflow-y-auto border-y border-line bg-bg/60 px-4 py-3">
        {query.isLoading && <Skeleton className="h-24" />}
        {query.isError && <ErrorState error={query.error} />}
        {messages.length === 0 && !query.isLoading && (
          <div className="space-y-2 py-6 text-center">
            <p className="text-[13px] text-ink-3">Namuna savollardan birini tanlang:</p>
            <div className="flex flex-wrap justify-center gap-1.5">
              {samples.map((s) => (
                <button key={s} type="button" onClick={() => send.mutate(s)} className="rounded-full border border-line bg-surface px-3 py-1 text-[12px] text-ink-2 hover:border-accent hover:text-accent">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={cn("flex", m.sender === "customer" ? "justify-end" : "justify-start")}>
            <div className={cn("max-w-[85%] rounded-2xl px-3 py-2 text-[13px] whitespace-pre-wrap", m.sender === "customer" ? "rounded-tr-md bg-accent text-white dark:text-[#0b1120]" : "rounded-tl-md border border-line bg-surface text-ink")}>
              {m.text}
              <div className={cn("mt-1 flex items-center gap-1.5 text-[10px]", m.sender === "customer" ? "text-white/70 dark:text-[#0b1120]/70" : "text-ink-3")}>
                {formatTime(m.created_at)}
                {m.is_demo && m.sender === "ai" && <span>· demo AI</span>}
                {m.tool_trace.length > 0 && <span>· {m.tool_trace.map((t) => t.tool).join(", ")}</span>}
              </div>
            </div>
          </div>
        ))}
      </div>
      <form className="flex gap-2 p-3" onSubmit={(e) => { e.preventDefault(); if (text.trim()) send.mutate(text.trim()); }}>
        <Input aria-label="Test xabari" placeholder="Mijoz sifatida yozing…" value={text} onChange={(e) => setText(e.target.value)} className="flex-1" />
        <Button type="submit" variant="primary" size="icon" loading={send.isPending} disabled={!text.trim()} aria-label="Yuborish">
          {!send.isPending && <Send className="size-4" />}
        </Button>
      </form>
    </Card>
  );
}

export default function AISettingsPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const { can } = useAuth();
  const editable = can("manager");
  const query = useQuery({ queryKey: ["ai", "settings"], queryFn: () => get<AISettings>("/ai/settings/") });
  const [form, setForm] = useState<AISettings | null>(null);
  const [greetLang, setGreetLang] = useState<"uz" | "ru" | "en">("uz");
  const [errors, setErrors] = useState<Record<string, string>>({});
  useEffect(() => {
    if (query.data) setForm(query.data);
  }, [query.data]);
  const save = useMutation({
    mutationFn: () => put<AISettings>("/ai/settings/", form),
    onSuccess: (d) => { setErrors({}); qc.setQueryData(["ai", "settings"], d); toast.success("AI sozlamalari saqlandi"); },
    onError: (e) => {
      if (e instanceof ApiError) setErrors(Object.fromEntries(Object.keys(e.fields).map((k) => [k, e.fieldError(k) ?? JSON.stringify(e.fields[k])])));
      toast.error("Saqlanmadi", errorMessage(e));
    },
  });
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} />;
  if (!form) return <Skeleton className="h-[600px]" />;
  const set = <K extends keyof AISettings>(k: K, v: AISettings[K]) => setForm({ ...form, [k]: v });

  return (
    <>
      <PageHeader
        title="AI sozlamalari"
        subtitle="Suhbat uslubi, tillar, ish vaqti va operatorga o'tkazish qoidalari"
        actions={
          editable && (
            <Button variant="primary" loading={save.isPending} onClick={() => save.mutate()}>
              O'zgarishlarni saqlash
            </Button>
          )
        }
      />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_440px]">
        <div className="space-y-4">
          <Card className="p-5">
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <Bot className="size-4 text-accent" aria-hidden />
              <span className="text-sm font-medium text-ink">Provider:</span>
              {form.provider.is_demo ? <Badge tone="warning" dot>Demo rejim — deterministik dialog (haqiqiy LLM emas)</Badge> : <Badge tone="accent">{form.provider.name} · {form.provider.model}</Badge>}
            </div>
            <fieldset disabled={!editable} className="space-y-5">
              <Switch checked={form.is_enabled} onChange={(v) => set("is_enabled", v)} label="AI avtomatik javob berishi" description="O'chirilsa, barcha yangi xabarlar operator navbatiga tushadi" />
              <div>
                <p className="mb-1.5 text-[13px] font-medium text-ink-2">Salomlashuv matni</p>
                <Tabs size="sm" value={greetLang} onChange={setGreetLang} items={[{ value: "uz", label: "O'zbekcha" }, { value: "ru", label: "Русский" }, { value: "en", label: "English" }]} />
                <Textarea className="mt-2" aria-label="Salomlashuv" value={form.greetings[greetLang] ?? ""} onChange={(e) => set("greetings", { ...form.greetings, [greetLang]: e.target.value })} maxLength={600} hint="{org} — tashkilot nomi bilan almashtiriladi" error={errors.greetings} />
              </div>
              <div>
                <p className="mb-1.5 text-[13px] font-medium text-ink-2">Suhbat tillari</p>
                <div className="flex flex-wrap gap-4">
                  {[{ v: "uz", l: "O'zbekcha (standart)" }, { v: "ru", l: "Русский" }, { v: "en", l: "English" }].map((o) => (
                    <Checkbox key={o.v} label={o.l} disabled={o.v === "uz"} checked={form.enabled_languages.includes(o.v)} onChange={(c) => set("enabled_languages", c ? [...form.enabled_languages, o.v] : form.enabled_languages.filter((x) => x !== o.v))} />
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <Select label="Uslub" value={form.tone} onChange={(e) => set("tone", e.target.value as AISettings["tone"])} options={[{ value: "friendly", label: "Samimiy" }, { value: "formal", label: "Rasmiy" }]} />
                <Input label="Eslatma (soat oldin)" type="number" min={1} max={48} value={form.reminder_hours_before} onChange={(e) => set("reminder_hours_before", Number(e.target.value))} error={errors.reminder_hours_before} />
                <Input label="Taklif qilinadigan slotlar" type="number" min={1} max={5} value={form.max_slots_to_offer} onChange={(e) => set("max_slots_to_offer", Number(e.target.value))} error={errors.max_slots_to_offer} />
              </div>
              <div>
                <p className="mb-1.5 text-[13px] font-medium text-ink-2">Xodimlar ish vaqti</p>
                <div className="grid grid-cols-2 gap-3 sm:max-w-sm">
                  <Input aria-label="Boshlanish" type="time" value={form.working_hours.start} onChange={(e) => set("working_hours", { ...form.working_hours, start: e.target.value })} />
                  <Input aria-label="Tugash" type="time" value={form.working_hours.end} onChange={(e) => set("working_hours", { ...form.working_hours, end: e.target.value })} />
                </div>
                <div className="mt-2 flex flex-wrap gap-3">
                  {WEEKDAYS_SHORT.map((w, i) => (
                    <Checkbox key={w} label={w} checked={form.working_hours.days.includes(i)} onChange={(c) => set("working_hours", { ...form.working_hours, days: c ? [...form.working_hours.days, i].sort() : form.working_hours.days.filter((d) => d !== i) })} />
                  ))}
                </div>
                {errors.working_hours && <p className="mt-1 text-[12px] text-danger-strong">{errors.working_hours}</p>}
              </div>
              <div className="space-y-4 rounded-xl border border-line p-4">
                <p className="text-sm font-semibold text-ink">Operatorga o'tkazish</p>
                <TagInput label="Kalit so'zlar (mijoz yozsa, darhol operatorga o'tadi)" value={form.handoff_keywords} onChange={(v) => set("handoff_keywords", v)} />
                {errors.handoff_keywords && <p className="text-[12px] text-danger-strong">{errors.handoff_keywords}</p>}
                <Input label="Javob topilmasa, necha urinishdan keyin o'tkazish" type="number" min={1} max={5} value={form.handoff_after_failed_attempts} onChange={(e) => set("handoff_after_failed_attempts", Number(e.target.value))} className="max-w-[120px]" />
                <Switch checked={form.handoff_outside_hours_notice} onChange={(v) => set("handoff_outside_hours_notice", v)} label="Ish vaqtidan tashqari ogohlantirish" description="Operatorga o'tkazilganda ish vaqti haqida xabar qo'shiladi" />
                <Switch checked={form.ask_phone_before_booking} onChange={(v) => set("ask_phone_before_booking", v)} label="Bron oldidan telefon so'rash" />
              </div>
            </fieldset>
          </Card>
          <Card className="p-5">
            <p className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
              <ShieldCheck className="size-4 text-success" aria-hidden /> O'zgartirib bo'lmaydigan xavfsizlik qoidalari
            </p>
            <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
              {SAFETY_RULES.map((r) => (
                <li key={r} className="rounded-lg border border-line bg-surface-2 px-3 py-2 text-[13px] text-ink-2">
                  {r}
                </li>
              ))}
            </ul>
          </Card>
        </div>
        {editable ? <TestChat /> : <Card className="p-5 text-[13px] text-ink-3">Test-chat menejer va egasi uchun ochiq.</Card>}
      </div>
    </>
  );
}
