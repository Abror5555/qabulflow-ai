import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Bot, ChevronDown, FileText, Hand, Info, Mic, RotateCcw, Search, Send, UserRound } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Input } from "../components/ui/Form";
import { Avatar, KeyValue, Segmented } from "../components/ui/Misc";
import { EmptyState, ErrorState, Skeleton } from "../components/ui/States";
import { useToast } from "../contexts/ToastContext";
import { errorMessage, get, post } from "../lib/api";
import { cn } from "../lib/cn";
import { bookingStatusTone, leadStatusTone } from "../lib/constants";
import { dateKey, formatDateTime, formatDayKey, formatPhone, formatTime, relativeTime } from "../lib/format";
import type { ConversationDetail, ConversationItem, Message, Paginated } from "../lib/types";

type Queue = "all" | "waiting" | "mine" | "ai";

function ChannelBadge({ channel }: { channel: string }) {
  return <Badge tone={channel === "telegram" ? "info" : "teal"}>{channel === "telegram" ? "Telegram" : "Veb-chat"}</Badge>;
}

function ConversationList({ activeId, onSelect }: { activeId: number | null; onSelect: (id: number) => void }) {
  const [queue, setQueue] = useState<Queue>("all");
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(search), 300);
    return () => window.clearTimeout(t);
  }, [search]);
  const query = useQuery({
    queryKey: ["conversations", "list", queue, debounced],
    queryFn: () =>
      get<Paginated<ConversationItem>>("/conversations/", {
        search: debounced || undefined,
        queue: queue === "waiting" ? "waiting" : undefined,
        assigned: queue === "mine" ? "me" : undefined,
        mode: queue === "ai" ? "ai" : undefined,
        page_size: 40,
      }),
    refetchInterval: 8000,
    placeholderData: keepPreviousData,
  });
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="space-y-2.5 border-b border-line p-3">
        <Input aria-label="Suhbat qidirish" placeholder="Mijoz yoki matn bo'yicha…" value={search} onChange={(e) => setSearch(e.target.value)} icon={<Search className="size-4" />} />
        <Segmented
          label="Navbat"
          value={queue}
          onChange={setQueue}
          className="w-full [&>button]:flex-1 [&>button]:justify-center"
          items={[
            { value: "all", label: "Barchasi" },
            { value: "waiting", label: "Kutmoqda" },
            { value: "mine", label: "Meniki" },
            { value: "ai", label: "AI" },
          ]}
        />
      </div>
      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto">
        {query.isLoading && <div className="space-y-2 p-3">{Array.from({ length: 7 }).map((_, i) => <Skeleton key={i} className="h-14" />)}</div>}
        {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}
        {query.data?.results.length === 0 && <EmptyState title="Suhbat topilmadi" className="py-12" />}
        <ul>
          {query.data?.results.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                onClick={() => onSelect(c.id)}
                aria-current={c.id === activeId ? "true" : undefined}
                className={cn("flex w-full gap-3 border-b border-line px-3 py-3 text-left transition-colors", c.id === activeId ? "bg-accent-soft" : "hover:bg-surface-2")}
              >
                <Avatar name={c.lead_name} tone={c.channel === "telegram" ? "accent" : "teal"} />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium text-ink">{c.lead_name}</span>
                    <span className="shrink-0 text-[11px] text-ink-3">{relativeTime(c.last_message_at)}</span>
                  </span>
                  <span className="mt-0.5 block truncate text-[12px] text-ink-3">{c.last_message_preview || "—"}</span>
                  <span className="mt-1.5 flex flex-wrap items-center gap-1.5">
                    {c.needs_attention && <Badge tone="danger" dot>Kutmoqda</Badge>}
                    <Badge tone={c.mode === "human" ? "warning" : "accent"} icon={c.mode === "human" ? <UserRound className="size-3" /> : <Bot className="size-3" />}>
                      {c.mode === "human" ? (c.assigned_to ? c.assigned_to.full_name.split(" ")[0] : "Operator") : "AI"}
                    </Badge>
                    <span className="text-[11px] text-ink-3">{c.channel === "telegram" ? "Telegram" : "Veb-chat"}</span>
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function MessageBubble({ m }: { m: Message }) {
  const [showTrace, setShowTrace] = useState(false);
  if (m.kind === "event" || (m.sender === "system" && m.kind !== "voice" && !m.text.startsWith("⏰"))) {
    return (
      <div className="my-2 flex justify-center">
        <span className="rounded-full border border-line bg-surface-2 px-3 py-1 text-[12px] text-ink-3">
          {m.text} · {formatTime(m.created_at)}
        </span>
      </div>
    );
  }
  const mine = m.sender !== "customer";
  return (
    <div className={cn("flex gap-2", mine ? "justify-end" : "justify-start")}>
      {!mine && <Avatar name="Mijoz" initials="M" size="sm" tone="neutral" />}
      <div className={cn("max-w-[82%] sm:max-w-[70%]")}>
        <div
          className={cn(
            "rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap",
            m.sender === "customer" && "rounded-tl-md border border-line bg-surface text-ink",
            m.sender === "ai" && "rounded-tr-md bg-accent-soft text-ink",
            m.sender === "operator" && "rounded-tr-md bg-teal-soft text-ink",
            m.sender === "system" && "rounded-tr-md border border-dashed border-line-strong bg-surface-2 text-ink",
          )}
        >
          {m.kind === "voice" && (
            <span className="mb-1 flex items-center gap-1.5 text-[12px] font-medium text-ink-3">
              <Mic className="size-3.5" aria-hidden /> Ovozli xabar
              {m.is_demo && <Badge tone="warning">Demo transkript</Badge>}
              {m.transcript_status === "low_confidence" && <Badge tone="warning">Noaniq</Badge>}
              {m.transcript_status === "failed" && <Badge tone="danger">Transkripsiya xatosi</Badge>}
            </span>
          )}
          {m.text}
          {m.attachments.map((a) => (
            <audio key={a.id} controls preload="none" src={a.download_url} className="mt-2 h-8 w-full max-w-[260px]" aria-label="Ovozli xabarni tinglash" />
          ))}
        </div>
        <div className={cn("mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-ink-3", mine && "justify-end")}>
          <span>{m.sender === "ai" ? "AI" : m.sender === "operator" ? m.author?.full_name ?? "Operator" : m.sender === "system" ? "Tizim" : "Mijoz"}</span>
          <span>· {formatTime(m.created_at)}</span>
          {m.sender === "ai" && m.is_demo && <Badge tone="warning" className="h-[18px] px-1.5 text-[10px]">Demo AI</Badge>}
          {m.ai_status === "failed" && <Badge tone="danger" className="h-[18px] px-1.5 text-[10px]">AI xatosi</Badge>}
          {m.ai_status === "skipped_human" && <span>· AI javob bermadi (operator rejimi)</span>}
          {m.delivery_status === "demo" && <span>· demo outbox</span>}
          {m.delivery_status === "failed" && <span className="text-danger-strong">· yetkazilmadi</span>}
          {m.sources.length > 0 && (
            <span className="inline-flex items-center gap-1">
              · <FileText className="size-3" aria-hidden /> {m.sources.map((s) => s.document_title).join(", ")}
            </span>
          )}
          {m.tool_trace.length > 0 && (
            <button type="button" onClick={() => setShowTrace((v) => !v)} className="inline-flex items-center gap-0.5 font-medium text-accent hover:underline" aria-expanded={showTrace}>
              · AI amallari ({m.tool_trace.length}) <ChevronDown className={cn("size-3 transition-transform", showTrace && "rotate-180")} />
            </button>
          )}
        </div>
        {showTrace && (
          <ul className="mt-1 space-y-0.5 rounded-lg border border-line bg-surface-2 p-2 font-mono text-[11px] text-ink-2">
            {m.tool_trace.map((t, i) => (
              <li key={i}>
                {t.ok ? "✓" : "•"} {t.tool} {t.status && `(${t.status})`}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function ChatPane({ id, onBack, onInfo }: { id: number; onBack: () => void; onInfo: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [text, setText] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const detail = useQuery({ queryKey: ["conversation", id], queryFn: () => get<ConversationDetail>(`/conversations/${id}/`), refetchInterval: 8000 });
  const messages = useQuery({ queryKey: ["conversation", id, "messages"], queryFn: () => get<{ results: Message[] }>(`/conversations/${id}/messages/`, { limit: 200 }), refetchInterval: 5000 });
  const count = messages.data?.results.length ?? 0;
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [count, id]);

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["conversation", id] });
    void qc.invalidateQueries({ queryKey: ["conversations"] });
  };
  const takeOver = useMutation({ mutationFn: () => post(`/conversations/${id}/take-over/`), onSuccess: () => { toast.success("Suhbat sizga o'tdi", "AI avtomatik javob berishni to'xtatdi."); refresh(); }, onError: (e) => toast.error("Bajarilmadi", errorMessage(e)) });
  const returnAi = useMutation({ mutationFn: () => post(`/conversations/${id}/return-to-ai/`), onSuccess: () => { toast.success("Suhbat AI'ga qaytarildi"); refresh(); }, onError: (e) => toast.error("Bajarilmadi", errorMessage(e)) });
  const reply = useMutation({
    mutationFn: () => post(`/conversations/${id}/reply/`, { text }),
    onSuccess: () => { setText(""); refresh(); },
    onError: (e) => toast.error("Xabar yuborilmadi", errorMessage(e)),
  });

  const conv = detail.data;
  const grouped = useMemo(() => {
    const out: { day: string; items: Message[] }[] = [];
    (messages.data?.results ?? []).forEach((m) => {
      const day = dateKey(m.created_at);
      if (!out.length || out[out.length - 1].day !== day) out.push({ day, items: [] });
      out[out.length - 1].items.push(m);
    });
    return out;
  }, [messages.data]);

  if (detail.isError) return <ErrorState error={detail.error} onRetry={() => detail.refetch()} />;
  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex items-center gap-3 border-b border-line px-4 py-3">
        <Button variant="ghost" size="icon-sm" className="lg:hidden" onClick={onBack} aria-label="Suhbatlar ro'yxatiga qaytish">
          <ArrowLeft className="size-4" />
        </Button>
        {conv ? (
          <>
            <Avatar name={conv.lead_name} tone={conv.channel === "telegram" ? "accent" : "teal"} />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-ink">{conv.lead_name}</p>
              <p className="flex items-center gap-1.5 text-[12px] text-ink-3">
                <ChannelBadge channel={conv.channel} />
                <span>{conv.mode === "human" ? `Operator: ${conv.assigned_to?.full_name ?? "biriktirilmagan"}` : "AI javob bermoqda"}</span>
              </p>
            </div>
            <div className="flex items-center gap-1.5">
              {conv.mode === "human" ? (
                <Button size="sm" icon={<RotateCcw className="size-3.5" />} onClick={() => returnAi.mutate()} loading={returnAi.isPending}>
                  <span className="hidden sm:inline">AI'ga qaytarish</span>
                  <span className="sm:hidden">AI</span>
                </Button>
              ) : (
                <Button size="sm" variant="primary" icon={<Hand className="size-3.5" />} onClick={() => takeOver.mutate()} loading={takeOver.isPending}>
                  Suhbatni olish
                </Button>
              )}
              <Button variant="ghost" size="icon-sm" className="xl:hidden" onClick={onInfo} aria-label="Mijoz ma'lumotlari">
                <Info className="size-4" />
              </Button>
            </div>
          </>
        ) : (
          <Skeleton className="h-9 w-48" />
        )}
      </header>
      <div ref={scrollRef} className="scroll-thin min-h-0 flex-1 space-y-3 overflow-y-auto bg-bg/60 px-4 py-4" aria-live="polite">
        {messages.isLoading && <Skeleton className="h-40" />}
        {grouped.map((g) => (
          <div key={g.day} className="space-y-3">
            <div className="flex justify-center">
              <span className="rounded-full bg-surface-3 px-2.5 py-0.5 text-[11px] font-medium text-ink-3">{formatDayKey(g.day, { weekday: true })}</span>
            </div>
            {g.items.map((m) => (
              <MessageBubble key={m.id} m={m} />
            ))}
          </div>
        ))}
      </div>
      <footer className="border-t border-line bg-surface p-3">
        {conv?.mode === "human" ? (
          <form
            className="flex items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (text.trim()) reply.mutate();
            }}
          >
            <label htmlFor="operator-reply" className="sr-only">
              Javob matni
            </label>
            <textarea
              id="operator-reply"
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  if (text.trim()) reply.mutate();
                }
              }}
              rows={1}
              placeholder={`${conv.channel === "telegram" ? "Telegram" : "Veb-chat"} orqali javob yozing… (Enter — yuborish)`}
              className="max-h-36 min-h-10 flex-1 resize-none rounded-xl border border-line bg-surface-2 px-3.5 py-2.5 text-sm text-ink focus:border-accent focus:outline-none"
            />
            <Button type="submit" variant="primary" size="icon" disabled={!text.trim()} loading={reply.isPending} aria-label="Yuborish">
              {!reply.isPending && <Send className="size-4" />}
            </Button>
          </form>
        ) : (
          <div className="flex flex-col items-start justify-between gap-2 rounded-xl border border-dashed border-line-strong bg-surface-2 px-4 py-3 sm:flex-row sm:items-center">
            <p className="text-[13px] text-ink-2">
              <Bot className="mr-1 inline size-4 text-accent" aria-hidden />
              AI rejimi: javob yozish uchun suhbatni o'zingizga oling — AI to'xtatiladi.
            </p>
            <Button size="sm" variant="primary" onClick={() => takeOver.mutate()} loading={takeOver.isPending}>
              Suhbatni olish
            </Button>
          </div>
        )}
      </footer>
    </div>
  );
}

function InfoPane({ id }: { id: number }) {
  const detail = useQuery({ queryKey: ["conversation", id], queryFn: () => get<ConversationDetail>(`/conversations/${id}/`) });
  const conv = detail.data;
  if (!conv) return <div className="p-4"><Skeleton className="h-64" /></div>;
  const l = conv.lead;
  return (
    <div className="scroll-thin h-full overflow-y-auto p-4">
      <div className="flex items-center gap-3">
        <Avatar name={l.display_name} size="lg" />
        <div className="min-w-0">
          <p className="truncate font-semibold text-ink">{l.display_name}</p>
          <Badge tone={leadStatusTone(l.status)} dot>{l.status_label}</Badge>
        </div>
      </div>
      <dl className="mt-4 divide-y divide-line">
        <KeyValue label="Telefon">{formatPhone(l.phone)}</KeyValue>
        <KeyValue label="Telegram">{l.telegram_username ? `@${l.telegram_username}` : ""}</KeyValue>
        <KeyValue label="Manba">{l.source_label}</KeyValue>
        <KeyValue label="Til">{{ uz: "O'zbekcha", ru: "Русский", en: "English" }[l.language]}</KeyValue>
        <KeyValue label="Kurs">{l.interested_course_name}</KeyValue>
        <KeyValue label="Filial">{l.branch_name}</KeyValue>
        <KeyValue label="Maqsad">{l.goal}</KeyValue>
        <KeyValue label="Qulay vaqt">{l.preferred_time}</KeyValue>
        <KeyValue label="Eslatma roziligi">{l.consent_reminders ? "Ha" : "Yo'q"}</KeyValue>
      </dl>
      <p className="mt-4 mb-2 text-[13px] font-medium text-ink-2">Bronlar</p>
      {l.bookings.length === 0 ? (
        <p className="text-[13px] text-ink-3">Hali bron yo'q</p>
      ) : (
        <ul className="space-y-2">
          {l.bookings.map((b) => (
            <li key={b.id}>
              <Link to={`/bookings?booking=${b.id}`} className="block rounded-lg border border-line p-2.5 hover:bg-surface-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[13px] font-medium text-ink">{b.course_name}</span>
                  <Badge tone={bookingStatusTone(b.status)}>{b.status_label}</Badge>
                </div>
                <p className="mt-0.5 text-[12px] text-ink-3">{b.branch_name} · {formatDateTime(b.starts_at)}</p>
              </Link>
            </li>
          ))}
        </ul>
      )}
      {conv.handoffs.length > 0 && (
        <>
          <p className="mt-4 mb-2 text-[13px] font-medium text-ink-2">Operatorga o'tkazishlar</p>
          <ul className="space-y-1.5 text-[12px] text-ink-3">
            {conv.handoffs.map((h) => (
              <li key={h.id}>
                {formatDateTime(h.created_at)} · {{ requested: "so'raldi", active: "operator suhbatda", returned: "AI'ga qaytarildi" }[h.status]} {h.taken_by && `· ${h.taken_by.full_name}`}
              </li>
            ))}
          </ul>
        </>
      )}
      <Link to={`/leads?lead=${l.id}`} className="mt-5 inline-flex text-[13px] font-medium text-accent hover:underline">
        Mijoz profilini ochish →
      </Link>
    </div>
  );
}

export default function ConversationsPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const activeId = id ? Number(id) : null;
  const [infoOpen, setInfoOpen] = useState(false);
  return (
    <Card className="flex h-[calc(100vh-150px)] min-h-[560px] overflow-hidden">
      <aside className={cn("w-full shrink-0 border-r border-line lg:block lg:w-[320px]", activeId ? "hidden" : "block")} aria-label="Suhbatlar ro'yxati">
        <ConversationList activeId={activeId} onSelect={(cid) => navigate(`/conversations/${cid}`)} />
      </aside>
      <section className={cn("min-w-0 flex-1", activeId ? "block" : "hidden lg:block")} aria-label="Suhbat">
        {activeId ? (
          <ChatPane id={activeId} onBack={() => navigate("/conversations")} onInfo={() => setInfoOpen((v) => !v)} />
        ) : (
          <EmptyState title="Suhbatni tanlang" body="Chapdagi ro'yxatdan suhbatni oching. «Kutmoqda» — operator javobini kutayotgan mijozlar." className="h-full" />
        )}
      </section>
      {activeId && (
        <aside className={cn("w-[300px] shrink-0 border-l border-line", infoOpen ? "fixed inset-y-0 right-0 z-50 block bg-surface shadow-modal xl:static xl:shadow-none" : "hidden xl:block")} aria-label="Mijoz ma'lumotlari">
          {infoOpen && (
            <div className="flex justify-end p-2 xl:hidden">
              <Button size="sm" variant="ghost" onClick={() => setInfoOpen(false)}>
                Yopish
              </Button>
            </div>
          )}
          <InfoPane id={activeId} />
        </aside>
      )}
    </Card>
  );
}
