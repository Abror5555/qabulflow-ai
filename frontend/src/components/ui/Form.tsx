import { ChevronDown } from "lucide-react";
import { forwardRef, useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { cn } from "../../lib/cn";

const control =
  "w-full rounded-[10px] border border-line bg-surface px-3 text-sm text-ink placeholder:text-ink-3 transition-colors hover:border-line-strong focus:border-accent focus:outline-none focus:ring-3 focus:ring-accent/15 disabled:cursor-not-allowed disabled:bg-surface-2 disabled:text-ink-3";

export function Field({ label, error, hint, children, htmlFor, required, className }: { label?: string; error?: string; hint?: string; children: ReactNode; htmlFor?: string; required?: boolean; className?: string }) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      {label && (
        <label htmlFor={htmlFor} className="text-[13px] font-medium text-ink-2">
          {label}
          {required && <span className="ml-0.5 text-danger-strong" aria-hidden>*</span>}
        </label>
      )}
      {children}
      {error ? (
        <p className="text-[12px] text-danger-strong" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p className="text-[12px] text-ink-3">{hint}</p>
      ) : null}
    </div>
  );
}

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
  icon?: ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input({ label, error, hint, icon, className, id, required, ...rest }, ref) {
  const autoId = useId();
  const inputId = id || autoId;
  const input = (
    <div className="relative">
      {icon && <span className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-ink-3">{icon}</span>}
      <input
        ref={ref}
        id={inputId}
        required={required}
        aria-invalid={!!error || undefined}
        className={cn(control, "h-9", icon && "pl-9", error && "border-danger-strong", className)}
        {...rest}
      />
    </div>
  );
  if (!label && !error && !hint) return input;
  return (
    <Field label={label} error={error} hint={hint} htmlFor={inputId} required={required}>
      {input}
    </Field>
  );
});

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  hint?: string;
  options: { value: string | number; label: string; disabled?: boolean }[];
  placeholder?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select({ label, error, hint, options, placeholder, className, id, required, ...rest }, ref) {
  const autoId = useId();
  const selectId = id || autoId;
  const select = (
    <div className="relative">
      <select ref={ref} id={selectId} required={required} aria-invalid={!!error || undefined} className={cn(control, "h-9 appearance-none pr-9", className)} {...rest}>
        {placeholder !== undefined && <option value="">{placeholder}</option>}
        {options.map((o) => (
          <option key={o.value} value={o.value} disabled={o.disabled}>
            {o.label}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-ink-3" aria-hidden />
    </div>
  );
  if (!label && !error && !hint) return select;
  return (
    <Field label={label} error={error} hint={hint} htmlFor={selectId} required={required}>
      {select}
    </Field>
  );
});

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea({ label, error, hint, className, id, required, ...rest }, ref) {
  const autoId = useId();
  const taId = id || autoId;
  const ta = <textarea ref={ref} id={taId} required={required} aria-invalid={!!error || undefined} className={cn(control, "min-h-[84px] py-2 leading-relaxed", className)} {...rest} />;
  if (!label && !error && !hint) return ta;
  return (
    <Field label={label} error={error} hint={hint} htmlFor={taId} required={required}>
      {ta}
    </Field>
  );
});

export function Switch({ checked, onChange, label, description, disabled, id }: { checked: boolean; onChange: (v: boolean) => void; label: string; description?: string; disabled?: boolean; id?: string }) {
  const autoId = useId();
  const switchId = id || autoId;
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="min-w-0">
        <label htmlFor={switchId} className="text-sm font-medium text-ink">
          {label}
        </label>
        {description && <p className="mt-0.5 text-[13px] text-ink-3">{description}</p>}
      </div>
      <button
        id={switchId}
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative mt-0.5 inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors disabled:opacity-50",
          checked ? "bg-accent" : "bg-line-strong",
        )}
      >
        <span className={cn("inline-block size-4 rounded-full bg-white shadow transition-transform", checked ? "translate-x-[18px]" : "translate-x-0.5")} />
      </button>
    </div>
  );
}

export function Checkbox({ checked, onChange, label, disabled }: { checked: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean }) {
  return (
    <label className={cn("inline-flex cursor-pointer items-center gap-2 text-sm text-ink", disabled && "cursor-not-allowed opacity-60")}>
      <input type="checkbox" className="size-4 rounded border-line-strong accent-[var(--accent)]" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  );
}
