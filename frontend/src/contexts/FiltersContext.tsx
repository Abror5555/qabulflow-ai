import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { addDays, todayKey } from "../lib/format";

export type RangePreset = "7d" | "30d" | "90d" | "month" | "custom";

export interface DateRange {
  preset: RangePreset;
  from: string;
  to: string;
}

interface FiltersValue {
  range: DateRange;
  setRange: (r: DateRange) => void;
  applyPreset: (p: Exclude<RangePreset, "custom">) => void;
  branchId: number | null;
  setBranchId: (id: number | null) => void;
}

const FiltersContext = createContext<FiltersValue | null>(null);

export function presetRange(p: Exclude<RangePreset, "custom">): DateRange {
  const to = todayKey();
  if (p === "7d") return { preset: p, from: addDays(to, -6), to };
  if (p === "90d") return { preset: p, from: addDays(to, -89), to };
  if (p === "month") return { preset: p, from: `${to.slice(0, 8)}01`, to };
  return { preset: "30d", from: addDays(to, -29), to };
}

function load(): { range: DateRange; branchId: number | null } {
  try {
    const raw = sessionStorage.getItem("qf-filters");
    if (raw) {
      const parsed = JSON.parse(raw);
      const range = parsed.range?.preset && parsed.range.preset !== "custom" ? presetRange(parsed.range.preset) : parsed.range;
      if (range?.from && range?.to) return { range, branchId: parsed.branchId ?? null };
    }
  } catch {
    // e'tiborsiz
  }
  return { range: presetRange("30d"), branchId: null };
}

export function FiltersProvider({ children }: { children: ReactNode }) {
  const initial = load();
  const [range, setRangeState] = useState<DateRange>(initial.range);
  const [branchId, setBranchState] = useState<number | null>(initial.branchId);

  const persist = (r: DateRange, b: number | null) => {
    try {
      sessionStorage.setItem("qf-filters", JSON.stringify({ range: r, branchId: b }));
    } catch {
      // e'tiborsiz
    }
  };

  const value = useMemo<FiltersValue>(
    () => ({
      range,
      branchId,
      setRange: (r) => {
        setRangeState(r);
        persist(r, branchId);
      },
      applyPreset: (p) => {
        const r = presetRange(p);
        setRangeState(r);
        persist(r, branchId);
      },
      setBranchId: (id) => {
        setBranchState(id);
        persist(range, id);
      },
    }),
    [range, branchId],
  );
  return <FiltersContext.Provider value={value}>{children}</FiltersContext.Provider>;
}

export function useFilters() {
  const ctx = useContext(FiltersContext);
  if (!ctx) throw new Error("useFilters FiltersProvider ichida");
  return ctx;
}
