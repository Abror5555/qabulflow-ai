import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { patch } from "../lib/api";

export type ThemeChoice = "light" | "dark" | "system";

interface ThemeValue {
  choice: ThemeChoice;
  resolved: "light" | "dark";
  setChoice: (c: ThemeChoice, persistRemote?: boolean) => void;
}

const ThemeContext = createContext<ThemeValue | null>(null);
const KEY = "qf-theme";

function readStored(): ThemeChoice {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "light" || v === "dark" || v === "system") return v;
  } catch {
    // brauzer xotirasi yopiq bo'lishi mumkin
  }
  return "system";
}

function systemDark() {
  return typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [choice, setChoiceState] = useState<ThemeChoice>(readStored);
  const [sysDark, setSysDark] = useState(systemDark);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => setSysDark(mq.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  const resolved: "light" | "dark" = choice === "system" ? (sysDark ? "dark" : "light") : choice;

  useEffect(() => {
    document.documentElement.classList.toggle("dark", resolved === "dark");
    document.documentElement.dataset.theme = resolved;
  }, [resolved]);

  const setChoice = useCallback((c: ThemeChoice, persistRemote = true) => {
    setChoiceState(c);
    try {
      localStorage.setItem(KEY, c);
    } catch {
      // e'tiborsiz
    }
    if (persistRemote) {
      patch("/auth/me/", { preferences: { theme: c } }).catch(() => undefined);
    }
  }, []);

  const value = useMemo(() => ({ choice, resolved, setChoice }), [choice, resolved, setChoice]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme ThemeProvider ichida");
  return ctx;
}
