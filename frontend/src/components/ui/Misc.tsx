import { ChevronLeft, ChevronRight, Info } from "lucide-react";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { cn } from "../../lib/cn";
import { Button } from "./Button";

export function Tabs<T extends string>({ value, onChange, items, className, size = "md" }: { value: T; onChange: (v: T) => void; items: { value: T; label: ReactNode; count?: number }[]; className?: string; size?: "sm" | "md" }) {
  return (
    <div role="tablist" className={cn("flex gap-1 overflow-x-auto border-b border-line scroll-thin", className)}>
      {items.map((item) => {
        const active = item.value === value;
        return (
          <button
            key={item.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(item.value)}
            className={cn(
              "relative -mb-px inline-flex shrink-0 items-center gap-2 border-b-2 px-3 font-medium whitespace-nowrap transition-colors",
              size === "md" ? "h-10 text-sm" : "h-9 text-[13px]",
              active ? "border-accent text-ink" : "border-transparent text-ink-3 hover:text-ink",
            )}
          >
            {item.label}
            {item.count !== undefined && <span className={cn("rounded-full px-1.5 text-[11px] tabular", active ? "bg-accent-soft text-accent-ink" : "bg-surface-3 text-ink-3")}>{item.count}</span>}
          </button>
        );
      })}
    </div>
  );
}

export function Segmented<T extends string>({ value, onChange, items, label, className }: { value: T; onChange: (v: T) => void; items: { value: T; label: ReactNode; icon?: ReactNode }[]; label: string; className?: string }) {
  return (
    <div role="radiogroup" aria-label={label} className={cn("inline-flex h-9 items-center rounded-[10px] border border-line bg-surface-2 p-0.5", className)}>
      {items.map((item) => {
        const active = item.value === value;
        return (
          <button
            key={item.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(item.value)}
            className={cn(
              "inline-flex h-full items-center gap-1.5 rounded-[8px] px-2.5 text-[13px] font-medium whitespace-nowrap transition-colors",
              active ? "bg-surface text-ink shadow-card" : "text-ink-3 hover:text-ink",
            )}
          >
            {item.icon}
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

export function Avatar({ initials, name, size = "md", tone = "accent" }: { initials?: string; name?: string; size?: "sm" | "md" | "lg"; tone?: "accent" | "teal" | "neutral" }) {
  const fromName = (name || "")
    .split(/\s+/)
    .filter((w) => /^\p{L}/u.test(w))
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  const text = initials || fromName || "?";
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full font-semibold",
        size === "sm" && "size-6 text-[10px]",
        size === "md" && "size-8 text-[12px]",
        size === "lg" && "size-11 text-sm",
        tone === "accent" && "bg-accent-soft text-accent-ink",
        tone === "teal" && "bg-teal-soft text-teal-ink",
        tone === "neutral" && "bg-surface-3 text-ink-2",
      )}
      aria-hidden={!name}
      title={name}
    >
      {text}
    </span>
  );
}

export function Pagination({ page, totalPages, count, onChange }: { page: number; totalPages: number; count: number; onChange: (p: number) => void }) {
  if (totalPages <= 1) return <p className="px-1 text-[13px] text-ink-3">Jami: {count}</p>;
  return (
    <nav className="flex items-center justify-between gap-3" aria-label="Sahifalar">
      <p className="text-[13px] text-ink-3 tabular">
        {page}/{totalPages} sahifa · jami {count}
      </p>
      <div className="flex gap-1">
        <Button size="icon-sm" variant="secondary" disabled={page <= 1} onClick={() => onChange(page - 1)} aria-label="Oldingi sahifa">
          <ChevronLeft className="size-4" />
        </Button>
        <Button size="icon-sm" variant="secondary" disabled={page >= totalPages} onClick={() => onChange(page + 1)} aria-label="Keyingi sahifa">
          <ChevronRight className="size-4" />
        </Button>
      </div>
    </nav>
  );
}

export function InfoTip({ text, label = "Ta'rif" }: { text: string; label?: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);
  return (
    <span ref={ref} className="relative inline-flex">
      <button
        type="button"
        className="rounded-full text-ink-3 hover:text-ink"
        aria-label={label}
        aria-describedby={open ? id : undefined}
        onClick={() => setOpen((v) => !v)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
      >
        <Info className="size-3.5" aria-hidden />
      </button>
      {open && (
        <span id={id} role="tooltip" className="anim-fade absolute top-6 left-1/2 z-40 w-64 -translate-x-1/2 rounded-lg border border-line bg-surface p-3 text-[12px] leading-relaxed font-normal text-ink-2 shadow-pop">
          {text}
        </span>
      )}
    </span>
  );
}

export function Menu({ trigger, children, align = "right", label }: { trigger: (props: { onClick: () => void; "aria-expanded": boolean; "aria-haspopup": "menu" }) => ReactNode; children: (close: () => void) => ReactNode; align?: "left" | "right"; label: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);
  return (
    <div ref={ref} className="relative">
      {trigger({ onClick: () => setOpen((v) => !v), "aria-expanded": open, "aria-haspopup": "menu" })}
      {open && (
        <div role="menu" aria-label={label} className={cn("anim-fade absolute top-full z-50 mt-1.5 min-w-[220px] rounded-xl border border-line bg-surface p-1.5 shadow-pop", align === "right" ? "right-0" : "left-0")}>
          {children(() => setOpen(false))}
        </div>
      )}
    </div>
  );
}

export function MenuItem({ onClick, children, icon, danger }: { onClick: () => void; children: ReactNode; icon?: ReactNode; danger?: boolean }) {
  return (
    <button type="button" role="menuitem" onClick={onClick} className={cn("flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm hover:bg-surface-3", danger ? "text-danger-strong" : "text-ink")}>
      {icon && <span className="text-ink-3">{icon}</span>}
      {children}
    </button>
  );
}

export function KeyValue({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 py-2 text-sm">
      <dt className="shrink-0 text-ink-3">{label}</dt>
      <dd className="min-w-0 text-right font-medium break-words text-ink">{children || "—"}</dd>
    </div>
  );
}
