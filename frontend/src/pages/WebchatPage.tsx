import { FileText, Loader2, Mic, Send, Square, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { cn } from "../lib/cn";
import { formatTime } from "../lib/format";

interface WidgetConfig {
  title: string;
  organization_name: string;
  accent_color: string;
  languages: string[];
  default_language: string;
  greetings: Record<string, string>;
  privacy: Record<string, string>;
  quick_replies: Record<string, string[]>;
  demo_mode: boolean;
  ai_demo: boolean;
  voice_enabled: boolean;
  audio_max_seconds: number;
}

interface PublicMessage {
  id: number;
  sender: "customer" | "ai" | "operator" | "system";
  sender_label: string;
  kind: string;
  text: string;
  is_demo: boolean;
  transcript_status: string;
  sources: { title: string; page: number | null }[];
  created_at: string;
}

const UI = {
  uz: { placeholder: "Xabaringizni yozing…", send: "Yuborish", typing: "Javob yozilmoqda…", record: "Ovozli xabar yozish", stop: "Yozishni to'xtatish", error: "Xabar yuborilmadi. Qayta urinib ko'ring.", ai: "AI yordamchi", operator: "Administrator", demo: "Demo", recording: "Yozilmoqda" },
  ru: { placeholder: "Напишите сообщение…", send: "Отправить", typing: "Печатает ответ…", record: "Записать голосовое", stop: "Остановить запись", error: "Не отправлено. Попробуйте ещё раз.", ai: "AI-помощник", operator: "Администратор", demo: "Демо", recording: "Запись" },
  en: { placeholder: "Type your message…", send: "Send", typing: "Typing a reply…", record: "Record voice message", stop: "Stop recording", error: "Not sent. Please try again.", ai: "AI assistant", operator: "Administrator", demo: "Demo", recording: "Recording" },
} as const;
type Lang = keyof typeof UI;

function storageKey(key: string) {
  return `qf-webchat-${key}`;
}

function readToken(key: string): string | null {
  try {
    return localStorage.getItem(storageKey(key));
  } catch {
    return null;
  }
}

function writeToken(key: string, token: string) {
  try {
    localStorage.setItem(storageKey(key), token);
  } catch {
    // brauzer xotirasi yopiq — sessiya faqat shu sahifa uchun
  }
}

export default function WebchatPage() {
  const { publicKey = "" } = useParams();
  const [params] = useSearchParams();
  const embed = params.get("embed") === "1";
  const [config, setConfig] = useState<WidgetConfig | null>(null);
  const [fatal, setFatal] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [lang, setLang] = useState<Lang>("uz");
  const [messages, setMessages] = useState<PublicMessage[]>([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [recSeconds, setRecSeconds] = useState(0);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startRef = useRef(0);
  const scrollRef = useRef<HTMLDivElement>(null);
  const t = UI[lang];
  const base = `/api/public/widget/${encodeURIComponent(publicKey)}`;

  useEffect(() => {
    document.title = "Chat";
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${base}/config/`);
        if (!res.ok) throw new Error((await res.json().catch(() => null))?.error?.message || "Vidjet topilmadi");
        const cfg: WidgetConfig = await res.json();
        if (cancelled) return;
        setConfig(cfg);
        document.title = cfg.title;
        const browserLang = navigator.language.slice(0, 2) as Lang;
        setLang(cfg.languages.includes(browserLang) ? browserLang : (cfg.default_language as Lang) || "uz");
        const existing = readToken(publicKey);
        const sres = await fetch(`${base}/session/`, { method: "POST", headers: existing ? { "X-Visitor-Token": existing } : {} });
        const session = await sres.json();
        if (cancelled) return;
        writeToken(publicKey, session.token);
        setToken(session.token);
      } catch (e) {
        setFatal((e as Error).message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [base, publicKey]);

  const lastId = messages.length ? messages[messages.length - 1].id : 0;
  const poll = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${base}/messages/${lastId ? `?after_id=${lastId}` : ""}`, { headers: { "X-Visitor-Token": token } });
      if (!res.ok) return;
      const data = await res.json();
      if (data.conversation?.language && !lastId) setLang(data.conversation.language);
      if (data.messages?.length) {
        setMessages((prev) => {
          const ids = new Set(prev.map((m) => m.id));
          return [...prev, ...data.messages.filter((m: PublicMessage) => !ids.has(m.id))];
        });
      }
    } catch {
      // tarmoq xatosi — keyingi so'rovda qayta urinadi
    }
  }, [base, token, lastId]);

  useEffect(() => {
    void poll();
    const id = window.setInterval(poll, 4000);
    return () => window.clearInterval(id);
  }, [poll]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages.length, sending]);

  const merge = (incoming: PublicMessage[]) =>
    setMessages((prev) => {
      const ids = new Set(prev.map((m) => m.id));
      return [...prev, ...incoming.filter((m) => !ids.has(m.id))].sort((a, b) => a.id - b.id);
    });

  const sendText = async (value: string) => {
    const body = value.trim();
    if (!body || !token || sending) return;
    setSending(true);
    setError(null);
    const clientId = crypto.randomUUID ? crypto.randomUUID() : String(Date.now());
    try {
      const res = await fetch(`${base}/messages/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Visitor-Token": token },
        body: JSON.stringify({ text: body, language: lang, client_message_id: clientId }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error?.message || t.error);
      setText("");
      merge([data.customer_message, ...data.replies]);
    } catch (e) {
      setError((e as Error).message || t.error);
    } finally {
      setSending(false);
    }
  };

  const changeLang = async (l: Lang) => {
    setLang(l);
    if (token) await fetch(`${base}/language/`, { method: "POST", headers: { "Content-Type": "application/json", "X-Visitor-Token": token }, body: JSON.stringify({ language: l }) }).catch(() => undefined);
  };

  const voiceSupported = typeof window !== "undefined" && "MediaRecorder" in window && !!navigator.mediaDevices?.getUserMedia;

  const stopRecording = useCallback(() => {
    recorderRef.current?.stop();
  }, []);

  useEffect(() => {
    if (!recording) return;
    const id = window.setInterval(() => {
      const s = Math.floor((Date.now() - startRef.current) / 1000);
      setRecSeconds(s);
      if (config && s >= Math.min(config.audio_max_seconds, 60)) stopRecording();
    }, 250);
    return () => window.clearInterval(id);
  }, [recording, config, stopRecording]);

  const startRecording = async () => {
    if (!token) return;
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => e.data.size && chunksRef.current.push(e.data);
      recorder.onstop = async () => {
        stream.getTracks().forEach((tr) => tr.stop());
        setRecording(false);
        const duration = (Date.now() - startRef.current) / 1000;
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        if (blob.size < 200) return;
        setSending(true);
        try {
          const fd = new FormData();
          const ext = (recorder.mimeType || "audio/webm").includes("ogg") ? "ogg" : (recorder.mimeType || "").includes("mp4") ? "m4a" : "webm";
          fd.append("audio", blob, `voice.${ext}`);
          fd.append("duration", String(duration));
          fd.append("language", lang);
          const res = await fetch(`${base}/voice/`, { method: "POST", headers: { "X-Visitor-Token": token }, body: fd });
          const data = await res.json();
          if (!res.ok) throw new Error(data?.error?.message || t.error);
          merge([data.customer_message, ...data.replies]);
        } catch (e) {
          setError((e as Error).message);
        } finally {
          setSending(false);
        }
      };
      recorderRef.current = recorder;
      startRef.current = Date.now();
      setRecSeconds(0);
      recorder.start();
      setRecording(true);
    } catch {
      setError(lang === "ru" ? "Нет доступа к микрофону — напишите текстом." : lang === "en" ? "Microphone unavailable — please type." : "Mikrofonga ruxsat yo'q — matn bilan yozing.");
    }
  };

  const accent = config?.accent_color || "#4F46E5";
  const quick = config?.quick_replies[lang] ?? [];
  const showQuick = messages.filter((m) => m.sender === "customer").length < 2;
  const greeting = config?.greetings[lang];
  const style = useMemo(() => ({ ["--wc-accent" as string]: accent }), [accent]);

  if (fatal) {
    return <div className="flex h-full items-center justify-center p-6 text-center text-sm text-ink-3">{fatal}</div>;
  }

  return (
    <div className={cn("flex h-full flex-col bg-bg", !embed && "sm:items-center sm:justify-center sm:p-6")} style={style}>
      <div className={cn("flex h-full w-full flex-col overflow-hidden bg-surface", !embed && "sm:h-[min(720px,92vh)] sm:max-w-[420px] sm:rounded-2xl sm:border sm:border-line sm:shadow-modal")}>
        <header className="flex items-center gap-3 px-4 py-3 text-white" style={{ background: accent }}>
          <span className="flex size-9 items-center justify-center rounded-full bg-white/20 text-sm font-bold">{(config?.title || "Q").slice(0, 1)}</span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[15px] font-semibold">{config?.title ?? "…"}</p>
            <p className="text-[12px] text-white/80">{t.ai}{config?.ai_demo ? ` · ${t.demo}` : ""}</p>
          </div>
          {config && config.languages.length > 1 && (
            <label>
              <span className="sr-only">Til / Язык / Language</span>
              <select value={lang} onChange={(e) => void changeLang(e.target.value as Lang)} className="h-8 rounded-lg border border-white/30 bg-white/15 px-2 text-[12px] font-medium text-white [&>option]:text-ink">
                {config.languages.map((l) => (
                  <option key={l} value={l}>
                    {{ uz: "O'zbekcha", ru: "Русский", en: "English" }[l]}
                  </option>
                ))}
              </select>
            </label>
          )}
          {embed && (
            <button type="button" onClick={() => window.parent.postMessage({ type: "qabulflow:close" }, "*")} className="rounded-lg p-1.5 hover:bg-white/15" aria-label="Yopish">
              <X className="size-4" />
            </button>
          )}
        </header>
        {config?.demo_mode && <div className="border-b border-[#fde68a] bg-[#fffbeb] px-4 py-1 text-center text-[11px] font-medium text-[#92400e] dark:border-[#4d3a12] dark:bg-[#2b2110] dark:text-[#fcd34d]">Demo maket · sintetik ma'lumotlar</div>}
        <div ref={scrollRef} className="scroll-thin flex-1 space-y-3 overflow-y-auto px-4 py-4" aria-live="polite">
          {greeting && (
            <div className="flex justify-start">
              <div className="max-w-[85%] rounded-2xl rounded-tl-md border border-line bg-surface-2 px-3.5 py-2.5 text-[14px] whitespace-pre-wrap text-ink">{greeting}</div>
            </div>
          )}
          {config && <p className="px-2 text-center text-[11px] text-ink-3">{config.privacy[lang]}</p>}
          {messages.map((m) => {
            if (m.kind === "event") {
              return (
                <p key={m.id} className="text-center text-[11px] text-ink-3">
                  {m.text}
                </p>
              );
            }
            const mine = m.sender === "customer";
            return (
              <div key={m.id} className={cn("flex", mine ? "justify-end" : "justify-start")}>
                <div className="max-w-[85%]">
                  <div
                    className={cn("rounded-2xl px-3.5 py-2.5 text-[14px] leading-relaxed whitespace-pre-wrap", mine ? "rounded-tr-md text-white" : "rounded-tl-md border border-line bg-surface-2 text-ink")}
                    style={mine ? { background: accent } : undefined}
                  >
                    {m.kind === "voice" && <span className="mb-0.5 flex items-center gap-1 text-[11px] opacity-80"><Mic className="size-3" aria-hidden /> {m.is_demo ? "Demo transkript" : "Ovozli xabar"}</span>}
                    {m.text}
                  </div>
                  <p className={cn("mt-1 flex flex-wrap items-center gap-1 text-[11px] text-ink-3", mine && "justify-end")}>
                    {!mine && <span>{m.sender === "operator" ? t.operator : m.sender === "ai" ? t.ai : m.sender_label}</span>}
                    <span>{formatTime(m.created_at)}</span>
                    {m.sources.map((s, i) => (
                      <span key={i} className="inline-flex items-center gap-0.5">
                        · <FileText className="size-3" aria-hidden /> {s.title}
                      </span>
                    ))}
                  </p>
                </div>
              </div>
            );
          })}
          {sending && (
            <p className="flex items-center gap-2 text-[12px] text-ink-3">
              <Loader2 className="size-3.5 animate-spin" aria-hidden /> {t.typing}
            </p>
          )}
        </div>
        {showQuick && quick.length > 0 && (
          <div className="scroll-thin flex gap-1.5 overflow-x-auto px-4 pb-2">
            {quick.map((q) => (
              <button key={q} type="button" disabled={sending || !token} onClick={() => void sendText(q)} className="shrink-0 rounded-full border border-line bg-surface px-3 py-1.5 text-[12px] font-medium text-ink-2 hover:border-[var(--wc-accent)] hover:text-ink disabled:opacity-50">
                {q}
              </button>
            ))}
          </div>
        )}
        {error && <p className="px-4 pb-1 text-[12px] text-danger-strong" role="alert">{error}</p>}
        <form
          className="flex items-end gap-2 border-t border-line p-3"
          onSubmit={(e) => {
            e.preventDefault();
            void sendText(text);
          }}
        >
          <label htmlFor="wc-input" className="sr-only">
            {t.placeholder}
          </label>
          {recording ? (
            <div className="flex h-10 flex-1 items-center gap-2 rounded-xl border border-danger-strong/40 bg-danger-soft px-3 text-[13px] text-danger-strong">
              <span className="size-2 animate-pulse rounded-full bg-danger-strong" aria-hidden /> {t.recording} · {recSeconds}s / {Math.min(config?.audio_max_seconds ?? 60, 60)}s
            </div>
          ) : (
            <textarea
              id="wc-input"
              rows={1}
              value={text}
              maxLength={2000}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void sendText(text);
                }
              }}
              placeholder={t.placeholder}
              className="max-h-32 min-h-10 flex-1 resize-none rounded-xl border border-line bg-surface-2 px-3.5 py-2.5 text-[14px] text-ink focus:border-[var(--wc-accent)] focus:outline-none"
            />
          )}
          {voiceSupported && config?.voice_enabled && !text.trim() ? (
            <button
              type="button"
              onClick={() => (recording ? stopRecording() : void startRecording())}
              disabled={sending || !token}
              className={cn("flex size-10 shrink-0 items-center justify-center rounded-xl text-white disabled:opacity-50", recording ? "bg-danger-strong" : "")}
              style={recording ? undefined : { background: accent }}
              aria-label={recording ? t.stop : t.record}
            >
              {recording ? <Square className="size-4" /> : <Mic className="size-4" />}
            </button>
          ) : (
            <button type="submit" disabled={sending || !text.trim() || !token} className="flex size-10 shrink-0 items-center justify-center rounded-xl text-white disabled:opacity-50" style={{ background: accent }} aria-label={t.send}>
              {sending ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
            </button>
          )}
        </form>
      </div>
    </div>
  );
}
