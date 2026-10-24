import { CircleAlert, Inbox, Loader2, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";
import { errorMessage } from "../../lib/api";
import { cn } from "../../lib/cn";
import { Button } from "./Button";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} aria-hidden />;
}

export function Spinner({ className, label = "Yuklanmoqda" }: { className?: string; label?: string }) {
  return (
    <span role="status" className={cn("inline-flex items-center gap-2 text-ink-3", className)}>
      <Loader2 className="size-4 animate-spin" aria-hidden />
      <span className="sr-only">{label}</span>
    </span>
  );
}

export function EmptyState({ title, body, icon, action, className }: { title: string; body?: ReactNode; icon?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-col items-center justify-center px-6 py-10 text-center", className)}>
      <span className="mb-3 flex size-11 items-center justify-center rounded-xl border border-line bg-surface-2 text-ink-3">{icon ?? <Inbox className="size-5" aria-hidden />}</span>
      <p className="font-medium text-ink">{title}</p>
      {body && <p className="mt-1 max-w-sm text-[13px] text-ink-3">{body}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry, className }: { error: unknown; onRetry?: () => void; className?: string }) {
  return (
    <div className={cn("flex flex-col items-center justify-center px-6 py-10 text-center", className)} role="alert">
      <span className="mb-3 flex size-11 items-center justify-center rounded-xl bg-danger-soft text-danger-strong">
        <CircleAlert className="size-5" aria-hidden />
      </span>
      <p className="font-medium text-ink">Ma'lumotni yuklab bo'lmadi</p>
      <p className="mt-1 max-w-sm text-[13px] text-ink-3">{errorMessage(error)}</p>
      {onRetry && (
        <Button className="mt-4" size="sm" onClick={onRetry} icon={<RefreshCw className="size-3.5" />}>
          Qayta urinish
        </Button>
      )}
    </div>
  );
}
