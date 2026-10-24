import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Copy, ExternalLink, KeyRound, Mic, RefreshCw, Send } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, CardHeader, PageHeader } from "../components/ui/Card";
import { Input, Select, Switch } from "../components/ui/Form";
import { ConfirmDialog } from "../components/ui/Overlay";
import { Pagination, Tabs } from "../components/ui/Misc";
import { EmptyState, ErrorState, Skeleton } from "../components/ui/States";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";
import { useToast } from "../contexts/ToastContext";
import { ApiError, errorMessage, get, patch, post } from "../lib/api";
import type { Tone } from "../lib/constants";
import { formatDateTime } from "../lib/format";
import type { IntegrationItem, Me, OutboxItem, Paginated, WidgetSettings } from "../lib/types";

type Tab = "integrations" | "widget" | "organization" | "profile" | "notifications";

const STATE_META: Record<IntegrationItem["state"], { label: string; tone: Tone }> = {
  not_configured: { label: "Sozlanmagan", tone: "neutral" },
  demo: { label: "Demo rejim", tone: "warning" },
  configured: { label: "Sozlangan, tekshirilmagan", tone: "info" },
  connected: { label: "Ulangan", tone: "success" },
  error: { label: "Xato", tone: "danger" },
};
const KIND_META = {
  telegram: { title: "Telegram bot", icon: Send },
  ai: { title: "AI provider", icon: Bot },
  stt: { title: "Speech-to-text", icon: Mic },
};

function Integrations() {
  const qc = useQueryClient();
  const toast = useToast();
  const { can } = useAuth();
  const [page, setPage] = useState(1);
  const status = useQuery({ queryKey: ["integrations"], queryFn: () => get<{ demo_mode: boolean; items: IntegrationItem[] }>("/integrations/status/") });
  const outbox = useQuery({ queryKey: ["outbox", page], queryFn: () => get<Paginated<OutboxItem>>("/outbox/", { page, page_size: 8 }) });
  const check = useMutation({
    mutationFn: (kind: "telegram" | "ai") => post<IntegrationItem>(`/integrations/${kind}/check/`),
    onSuccess: (r) => { toast.success("Tekshirildi", `${KIND_META[r.kind].title}: ${STATE_META[r.state].label}`); void qc.invalidateQueries({ queryKey: ["integrations"] }); },
    onError: (e) => toast.error("Tekshirilmadi", errorMessage(e)),
  });
  if (status.isError) return <ErrorState error={status.error} onRetry={() => status.refetch()} />;
  return (
    <div className="space-y-4">
      {status.data?.demo_mode && (
        <div className="rounded-xl border border-[#fcd34d] bg-[#fffbeb] px-4 py-3 text-[13px] text-[#92400e] dark:border-[#78350f] dark:bg-[#2b2110] dark:text-[#fcd34d]">
          <b>DEMO_MODE yoqilgan.</b> Tashqi xabarlar hech kimga yuborilmaydi — ular pastdagi «Demo outbox»da ko'rinadi. Haqiqiy integratsiya uchun .env faylida kalitlarni kiriting va DEMO_MODE=false qiling.
        </div>
      )}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        {status.isLoading && Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-44" />)}
        {status.data?.items.map((item) => {
          const meta = KIND_META[item.kind];
          const st = STATE_META[item.state];
          return (
            <Card key={item.kind} className="flex flex-col p-4">
              <div className="flex items-start justify-between gap-2">
                <span className="flex items-center gap-2.5">
                  <span className="flex size-9 items-center justify-center rounded-lg bg-accent-soft text-accent-ink"><meta.icon className="size-4" aria-hidden /></span>
                  <span>
                    <span className="block font-semibold text-ink">{meta.title}</span>
                    <span className="block text-[12px] text-ink-3">
                      {item.kind === "telegram" ? `Rejim: ${item.mode === "webhook" ? "webhook (production)" : "long polling (development)"}` : `${item.provider}${item.model ? ` · ${item.model}` : ""}`}
                    </span>
                  </span>
                </span>
                <Badge tone={st.tone} dot>{st.label}</Badge>
              </div>
              <p className="mt-3 flex-1 text-[13px] text-ink-2">{item.note}</p>
              {item.bot_username && <p className="mt-1 text-[13px] text-ink-2">Bot: @{item.bot_username}</p>}
              {item.last_checked_at && <p className="mt-1 text-[12px] text-ink-3">Oxirgi tekshiruv: {formatDateTime(item.last_checked_at)}</p>}
              {can("owner") && item.kind !== "stt" && (
                <Button className="mt-3 self-start" size="sm" icon={<RefreshCw className="size-3.5" />} loading={check.isPending && check.variables === item.kind} onClick={() => check.mutate(item.kind as "telegram" | "ai")}>
                  Ulanishni tekshirish
                </Button>
              )}
            </Card>
          );
        })}
      </div>
      <Card>
        <CardHeader title="Tashqi xabarlar navbati (outbox)" subtitle="Takroriy jo'natishdan himoyalangan. Demo rejimida xabarlar faqat shu yerda saqlanadi." />
        <div className="px-5 pb-5">
          {outbox.isError ? <ErrorState error={outbox.error} /> : outbox.isLoading ? <Skeleton className="h-40" /> : outbox.data!.results.length === 0 ? <EmptyState title="Navbat bo'sh" /> : (
            <>
              <ul className="divide-y divide-line">
                {outbox.data!.results.map((o) => (
                  <li key={o.id} className="flex flex-col gap-1 py-2.5 sm:flex-row sm:items-start sm:gap-4">
                    <span className="w-[140px] shrink-0 text-[12px] text-ink-3">{formatDateTime(o.created_at)}</span>
                    <span className="min-w-0 flex-1 text-[13px] whitespace-pre-line text-ink line-clamp-3">{o.text}</span>
                    <span className="flex shrink-0 items-center gap-1.5">
                      <Badge tone="neutral">{{ reply: "Javob", reminder: "Eslatma", system: "Tizim" }[o.kind] ?? o.kind}</Badge>
                      <Badge tone={o.status === "sent" ? "success" : o.status === "demo" ? "warning" : o.status === "failed" ? "danger" : "info"}>{{ demo: "Demo outbox", sent: "Yuborildi", failed: "Xato", queued: "Navbatda", sending: "Yuborilmoqda" }[o.status] ?? o.status}</Badge>
                    </span>
                  </li>
                ))}
              </ul>
              <div className="mt-3"><Pagination page={outbox.data!.page} totalPages={outbox.data!.total_pages} count={outbox.data!.count} onChange={setPage} /></div>
            </>
          )}
        </div>
      </Card>
    </div>
  );
}

function Widget() {
  const qc = useQueryClient();
  const toast = useToast();
  const { can } = useAuth();
  const editable = can("owner");
  const query = useQuery({ queryKey: ["widget"], queryFn: () => get<WidgetSettings>("/widget/") });
  const [form, setForm] = useState<WidgetSettings | null>(null);
  const [origins, setOrigins] = useState("");
  const [rotateOpen, setRotateOpen] = useState(false);
  useEffect(() => {
    if (query.data) { setForm(query.data); setOrigins(query.data.allowed_origins.join("\n")); }
  }, [query.data]);
  const save = useMutation({
    mutationFn: () => patch<WidgetSettings>("/widget/", { title: form!.title, accent_color: form!.accent_color, position: form!.position, is_enabled: form!.is_enabled, allowed_origins: origins.split(/\s+/).filter(Boolean) }),
    onSuccess: (d) => { qc.setQueryData(["widget"], d); toast.success("Vidjet sozlamalari saqlandi"); },
    onError: (e) => toast.error("Saqlanmadi", e instanceof ApiError ? e.fieldError("allowed_origins") || e.message : errorMessage(e)),
  });
  const rotate = useMutation({ mutationFn: () => post<WidgetSettings>("/widget/rotate-key/"), onSuccess: (d) => { qc.setQueryData(["widget"], d); setRotateOpen(false); toast.success("Yangi kalit yaratildi", "Saytdagi kodni yangilang."); } });
  if (!form) return <Skeleton className="h-80" />;
  const copy = async () => {
    try { await navigator.clipboard.writeText(form.embed_code); toast.success("Kod nusxalandi"); } catch { toast.error("Nusxalab bo'lmadi"); }
  };
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Card className="p-5">
        <fieldset disabled={!editable} className="space-y-4">
          <Switch checked={form.is_enabled} onChange={(v) => setForm({ ...form, is_enabled: v })} label="Vidjet yoqilgan" />
          <Input label="Sarlavha" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          <div className="grid grid-cols-2 gap-3">
            <Input label="Rang" type="color" value={form.accent_color} onChange={(e) => setForm({ ...form, accent_color: e.target.value })} className="h-9 p-1" />
            <Select label="Joylashuv" value={form.position} onChange={(e) => setForm({ ...form, position: e.target.value as "left" | "right" })} options={[{ value: "right", label: "O'ng pastda" }, { value: "left", label: "Chap pastda" }]} />
          </div>
          <label className="block">
            <span className="text-[13px] font-medium text-ink-2">Ruxsat etilgan saytlar (har qatorda bitta)</span>
            <textarea value={origins} onChange={(e) => setOrigins(e.target.value)} rows={3} placeholder="https://markaz.uz" className="mt-1.5 w-full rounded-[10px] border border-line bg-surface px-3 py-2 font-mono text-[13px] text-ink" />
            <span className="text-[12px] text-ink-3">Bo'sh bo'lsa — barcha saytlarda ishlaydi. Faqat shu manzillar iframe'da ochishi mumkin.</span>
          </label>
          {editable && <Button variant="primary" loading={save.isPending} onClick={() => save.mutate()}>Saqlash</Button>}
        </fieldset>
      </Card>
      <Card className="p-5">
        <p className="text-sm font-semibold text-ink">Saytga qo'shish kodi</p>
        <pre className="mt-2 overflow-x-auto rounded-lg border border-line bg-surface-2 p-3 font-mono text-[12px] text-ink">{form.embed_code}</pre>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button size="sm" icon={<Copy className="size-3.5" />} onClick={copy}>Nusxalash</Button>
          <a href={`/chat/${form.public_key}`} target="_blank" rel="noreferrer" className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-line px-3 text-[13px] font-medium text-ink hover:bg-surface-2"><ExternalLink className="size-3.5" /> Veb-chatni ochish</a>
          <a href="/demo-site/" target="_blank" rel="noreferrer" className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-line px-3 text-[13px] font-medium text-ink hover:bg-surface-2"><ExternalLink className="size-3.5" /> Demo saytda ko'rish</a>
          {editable && <Button size="sm" variant="ghost" icon={<KeyRound className="size-3.5" />} onClick={() => setRotateOpen(true)}>Kalitni yangilash</Button>}
        </div>
        <p className="mt-3 text-[12px] text-ink-3">Ochiq kalit: <code className="font-mono">{form.public_key}</code> — u maxfiy emas, lekin yangilansa eski kod ishlamay qoladi.</p>
      </Card>
      <ConfirmDialog open={rotateOpen} onClose={() => setRotateOpen(false)} onConfirm={() => rotate.mutate()} loading={rotate.isPending} danger title="Vidjet kalitini yangilaysizmi?" body="Saytlaringizdagi eski kod ishlashdan to'xtaydi; yangi kodni joylashtirishingiz kerak bo'ladi." confirmLabel="Yangilash" />
    </div>
  );
}

const TIMEZONES = ["Asia/Tashkent", "Asia/Samarkand", "Asia/Almaty", "Europe/Moscow", "Asia/Dubai", "UTC"];

function Organization() {
  const toast = useToast();
  const { can, refresh } = useAuth();
  const query = useQuery({ queryKey: ["organization"], queryFn: () => get<{ name: string; timezone: string; default_language: string; slug: string; currency: string }>("/organization/") });
  const [form, setForm] = useState({ name: "", timezone: "Asia/Tashkent", default_language: "uz" });
  useEffect(() => { if (query.data) setForm({ name: query.data.name, timezone: query.data.timezone, default_language: query.data.default_language }); }, [query.data]);
  const save = useMutation({ mutationFn: () => patch("/organization/", form), onSuccess: () => { toast.success("Tashkilot sozlamalari saqlandi"); refresh(); }, onError: (e) => toast.error("Saqlanmadi", errorMessage(e)) });
  if (!query.data) return <Skeleton className="h-60" />;
  return (
    <Card className="max-w-2xl p-5">
      <fieldset disabled={!can("owner")} className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Input className="sm:col-span-2" label="Tashkilot nomi" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <Select label="Vaqt zonasi" value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} options={TIMEZONES.map((t) => ({ value: t, label: t }))} hint="Sanalar UTC'da saqlanadi va shu zonada ko'rsatiladi" />
        <Select label="Standart suhbat tili" value={form.default_language} onChange={(e) => setForm({ ...form, default_language: e.target.value })} options={[{ value: "uz", label: "O'zbekcha" }, { value: "ru", label: "Русский" }, { value: "en", label: "English" }]} />
        <Input label="Valyuta" value={query.data.currency} disabled />
        <Input label="Identifikator" value={query.data.slug} disabled />
        {can("owner") && <div className="sm:col-span-2"><Button variant="primary" loading={save.isPending} onClick={() => save.mutate()}>Saqlash</Button></div>}
      </fieldset>
    </Card>
  );
}

function Profile() {
  const { me, refresh } = useAuth();
  const { choice, setChoice } = useTheme();
  const toast = useToast();
  const [name, setName] = useState(me?.full_name ?? "");
  const [pw, setPw] = useState({ current_password: "", new_password: "" });
  const [pwErr, setPwErr] = useState<Record<string, string>>({});
  const saveName = useMutation({ mutationFn: () => patch<Me>("/auth/me/", { full_name: name }), onSuccess: () => { toast.success("Profil saqlandi"); refresh(); }, onError: (e) => toast.error("Saqlanmadi", errorMessage(e)) });
  const changePw = useMutation({
    mutationFn: () => post("/auth/change-password/", pw),
    onSuccess: () => { toast.success("Parol o'zgartirildi"); setPw({ current_password: "", new_password: "" }); setPwErr({}); },
    onError: (e) => {
      if (e instanceof ApiError) setPwErr(Object.fromEntries(Object.keys(e.fields).map((k) => [k, e.fieldError(k) ?? ""])));
      toast.error("Parol o'zgarmadi", errorMessage(e));
    },
  });
  return (
    <div className="grid max-w-4xl grid-cols-1 gap-4 lg:grid-cols-2">
      <Card className="space-y-3 p-5">
        <p className="text-sm font-semibold text-ink">Profil</p>
        <Input label="To'liq ism" value={name} onChange={(e) => setName(e.target.value)} />
        <Input label="Email" value={me?.email ?? ""} disabled />
        <Select label="Mavzu" value={choice} onChange={(e) => setChoice(e.target.value as "light" | "dark" | "system")} options={[{ value: "light", label: "Yorug'" }, { value: "dark", label: "Qorong'i" }, { value: "system", label: "Tizim bo'yicha" }]} hint="Tanlov saqlanadi" />
        <Button variant="primary" loading={saveName.isPending} onClick={() => saveName.mutate()}>Saqlash</Button>
      </Card>
      <Card className="space-y-3 p-5">
        <p className="text-sm font-semibold text-ink">Parolni o'zgartirish</p>
        {me?.is_demo_user && <p className="text-[13px] text-ink-3">Demo hisob paroli o'zgartirilmaydi.</p>}
        <Input label="Joriy parol" type="password" autoComplete="current-password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} error={pwErr.current_password} disabled={me?.is_demo_user} />
        <Input label="Yangi parol" type="password" autoComplete="new-password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} error={pwErr.new_password} hint="Kamida 8 belgi, oddiy bo'lmasin" disabled={me?.is_demo_user} />
        <Button variant="primary" loading={changePw.isPending} disabled={me?.is_demo_user || !pw.current_password || !pw.new_password} onClick={() => changePw.mutate()}>Parolni yangilash</Button>
      </Card>
    </div>
  );
}

const NOTIF_LABELS: Record<string, { label: string; description: string }> = {
  new_booking: { label: "Yangi sinov darsi broni", description: "AI yoki operator bron yaratganda" },
  booking_cancelled: { label: "Bron bekor qilindi", description: "Mijoz yoki xodim bekor qilganda" },
  handoff_requested: { label: "Mijoz operator kutmoqda", description: "AI suhbatni operatorga o'tkazganda" },
  ai_error: { label: "AI xatosi", description: "Provider javob bera olmaganda" },
  new_lead: { label: "Har bir yangi mijoz", description: "Ko'p bo'lishi mumkin" },
};

function Notifications() {
  const { me, refresh } = useAuth();
  const toast = useToast();
  const [prefs, setPrefs] = useState<Record<string, boolean>>(me?.notification_prefs ?? {});
  const save = useMutation({ mutationFn: (p: Record<string, boolean>) => patch("/auth/notification-prefs/", p), onSuccess: () => { toast.success("Bildirishnoma sozlamalari saqlandi"); refresh(); }, onError: (e) => toast.error("Saqlanmadi", errorMessage(e)) });
  return (
    <Card className="max-w-2xl divide-y divide-line">
      {Object.entries(NOTIF_LABELS).map(([key, meta]) => (
        <div key={key} className="p-4">
          <Switch checked={!!prefs[key]} onChange={(v) => { const next = { ...prefs, [key]: v }; setPrefs(next); save.mutate(next); }} label={meta.label} description={meta.description} />
        </div>
      ))}
    </Card>
  );
}

export default function SettingsPage() {
  const [params, setParams] = useSearchParams();
  const { can } = useAuth();
  const tab = (params.get("tab") as Tab) || (can("manager") ? "integrations" : "profile");
  const items: { value: Tab; label: string }[] = [
    ...(can("manager") ? [{ value: "integrations" as Tab, label: "Integratsiyalar" }, { value: "widget" as Tab, label: "Veb-chat vidjeti" }] : []),
    { value: "organization", label: "Tashkilot" },
    { value: "profile", label: "Profil" },
    { value: "notifications", label: "Bildirishnomalar" },
  ];
  return (
    <>
      <PageHeader title="Integratsiyalar va sozlamalar" subtitle="Telegram va AI ulanishining haqiqiy holati, vidjet, tashkilot va profil" />
      <Tabs className="mb-4" value={tab} onChange={(v) => setParams({ tab: v })} items={items} />
      {tab === "integrations" && <Integrations />}
      {tab === "widget" && <Widget />}
      {tab === "organization" && <Organization />}
      {tab === "profile" && <Profile />}
      {tab === "notifications" && <Notifications />}
    </>
  );
}
