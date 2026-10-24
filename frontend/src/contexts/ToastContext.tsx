import { CheckCircle2, Info, TriangleAlert, X } from "lucide-react";
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { cn } from "../lib/cn";

type ToastKind = "success" | "error" | "info";
interface ToastItem {
  id: number;
  kind: ToastKind;
  title: string;
  body?: string;
}

interface ToastValue {
  toast: (kind: ToastKind, title: string, body?: string) => void;
  success: (title: string, body?: string) => void;
  error: (title: string, body?: string) => void;
}

const ToastContext = createContext<ToastValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const counter = useRef(0);

  const remove = useCallback((id: number) => setItems((list) => list.filter((t) => t.id !== id)), []);

  const toast = useCallback(
    (kind: ToastKind, title: string, body?: string) => {
      const id = ++counter.current;
      setItems((list) => [...list.slice(-3), { id, kind, title, body }]);
      window.setTimeout(() => remove(id), kind === "error" ? 6500 : 4000);
    },
    [remove],
  );

  const value = useMemo(
    () => ({ toast, success: (t: string, b?: string) => toast("success", t, b), error: (t: string, b?: string) => toast("error", t, b) }),
    [toast],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-4 z-[70] flex flex-col items-center gap-2 px-4 sm:inset-x-auto sm:right-4 sm:items-end" aria-live="polite" role="status">
        {items.map((t) => {
          const Icon = t.kind === "success" ? CheckCircle2 : t.kind === "error" ? TriangleAlert : Info;
          return (
            <div
              key={t.id}
              className={cn(
                "anim-fade pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl border bg-surface p-3.5 shadow-pop",
                t.kind === "error" ? "border-danger/30" : "border-line",
              )}
            >
              <Icon className={cn("mt-0.5 size-5 shrink-0", t.kind === "success" && "text-success", t.kind === "error" && "text-danger-strong", t.kind === "info" && "text-accent")} aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="font-medium text-ink">{t.title}</p>
                {t.body && <p className="mt-0.5 text-[13px] text-ink-2">{t.body}</p>}
              </div>
              <button type="button" onClick={() => remove(t.id)} className="rounded-md p-1 text-ink-3 hover:bg-surface-3 hover:text-ink" aria-label="Yopish">
                <X className="size-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast ToastProvider ichida");
  return ctx;
}
