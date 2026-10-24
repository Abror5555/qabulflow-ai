import type { ReactNode } from "react";
import type { Tone } from "../../lib/constants";
import { cn } from "../../lib/cn";

const tones: Record<Tone, string> = {
  neutral: "bg-surface-3 text-ink-2 border-line",
  info: "bg-info-soft text-[#1d4ed8] border-[#bfdbfe] dark:text-[#93c5fd] dark:border-[#1e3a5f]",
  accent: "bg-accent-soft text-accent-ink border-[#c7d2fe] dark:border-[#2e3577]",
  teal: "bg-teal-soft text-teal-ink border-[#99e6dc] dark:border-[#134e48]",
  success: "bg-success-soft text-success border-[#bbf0cf] dark:border-[#1f4d31]",
  successStrong: "bg-[#dcfce7] text-[#166534] border-[#86efac] dark:bg-[#14361f] dark:text-[#86efac] dark:border-[#1f5c34]",
  warning: "bg-warning-soft text-warning border-[#fde68a] dark:border-[#4d3a12]",
  danger: "bg-danger-soft text-danger-strong border-[#fecaca] dark:border-[#5c2121]",
};

const dots: Record<Tone, string> = {
  neutral: "bg-ink-3",
  info: "bg-[#3b82f6]",
  accent: "bg-accent",
  teal: "bg-teal",
  success: "bg-success",
  successStrong: "bg-[#16a34a]",
  warning: "bg-[#f59e0b]",
  danger: "bg-danger-strong",
};

export function Badge({ tone = "neutral", children, dot, className, icon }: { tone?: Tone; children: ReactNode; dot?: boolean; className?: string; icon?: ReactNode }) {
  return (
    <span className={cn("inline-flex h-[22px] items-center gap-1.5 rounded-full border px-2 text-[12px] font-medium whitespace-nowrap", tones[tone], className)}>
      {dot && <span className={cn("size-1.5 rounded-full", dots[tone])} aria-hidden />}
      {icon}
      {children}
    </span>
  );
}

export function DemoBadge({ className, label = "Demo ma'lumotlar" }: { className?: string; label?: string }) {
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1.5 rounded-full border border-[#fcd34d] bg-[#fffbeb] px-2.5 text-[12px] font-semibold text-[#92400e] dark:border-[#78350f] dark:bg-[#2b2110] dark:text-[#fcd34d]",
        className,
      )}
      title="Barcha ko'rsatkichlar sintetik demo ma'lumotlardan hisoblangan"
    >
      <span className="size-1.5 rounded-full bg-[#f59e0b]" aria-hidden />
      {label}
    </span>
  );
}
