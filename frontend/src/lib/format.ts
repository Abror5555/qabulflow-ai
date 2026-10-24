/** Sana, vaqt va son formatlash. Barcha sanalar tashkilot vaqt zonasida ko'rsatiladi. */

let orgTimeZone = "Asia/Tashkent";

export function setOrgTimeZone(tz: string | undefined | null) {
  if (tz) orgTimeZone = tz;
}

export function getOrgTimeZone() {
  return orgTimeZone;
}

const MONTHS = ["yan", "fev", "mar", "apr", "may", "iyn", "iyl", "avg", "sen", "okt", "noy", "dek"];
const MONTHS_FULL = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"];
export const WEEKDAYS_SHORT = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"];
export const WEEKDAYS_FULL = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"];

export interface ZonedParts {
  year: number;
  month: number; // 1-12
  day: number;
  hour: number;
  minute: number;
  weekday: number; // 0=Dushanba
}

const partsCache = new Map<string, Intl.DateTimeFormat>();

function formatter(tz: string) {
  let f = partsCache.get(tz);
  if (!f) {
    f = new Intl.DateTimeFormat("en-GB", {
      timeZone: tz,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      weekday: "short",
      hourCycle: "h23",
    });
    partsCache.set(tz, f);
  }
  return f;
}

const WD: Record<string, number> = { Mon: 0, Tue: 1, Wed: 2, Thu: 3, Fri: 4, Sat: 5, Sun: 6 };

export function zoned(iso: string | Date, tz = orgTimeZone): ZonedParts {
  const date = typeof iso === "string" ? new Date(iso) : iso;
  const parts = Object.fromEntries(formatter(tz).formatToParts(date).map((p) => [p.type, p.value]));
  return {
    year: Number(parts.year),
    month: Number(parts.month),
    day: Number(parts.day),
    hour: Number(parts.hour),
    minute: Number(parts.minute),
    weekday: WD[parts.weekday as string] ?? 0,
  };
}

const pad = (n: number) => String(n).padStart(2, "0");

export function dateKey(iso: string | Date, tz = orgTimeZone): string {
  const p = zoned(iso, tz);
  return `${p.year}-${pad(p.month)}-${pad(p.day)}`;
}

export function todayKey(): string {
  return dateKey(new Date());
}

export function formatTime(iso: string): string {
  const p = zoned(iso);
  return `${pad(p.hour)}:${pad(p.minute)}`;
}

export function formatDate(iso: string, opts: { withYear?: boolean } = {}): string {
  const p = zoned(iso);
  return `${p.day}-${MONTHS[p.month - 1]}${opts.withYear ? ` ${p.year}` : ""}`;
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return `${formatDate(iso)}, ${formatTime(iso)}`;
}

export function formatDayKey(key: string, opts: { weekday?: boolean; year?: boolean } = {}): string {
  const [y, m, d] = key.split("-").map(Number);
  const wd = (new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7;
  return `${opts.weekday ? `${WEEKDAYS_SHORT[wd]}, ` : ""}${d}-${MONTHS[m - 1]}${opts.year ? ` ${y}` : ""}`;
}

export function monthTitle(year: number, month: number): string {
  return `${MONTHS_FULL[month - 1]} ${year}`;
}

export function relativeTime(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 45) return "hozirgina";
  if (diff < 3600) return `${Math.round(diff / 60)} daq oldin`;
  if (diff < 86400) return `${Math.round(diff / 3600)} soat oldin`;
  if (diff < 86400 * 7) return `${Math.round(diff / 86400)} kun oldin`;
  return formatDate(iso);
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("ru-RU").format(value).replace(/[\u00a0\u202f]/g, " ");
}

export function formatCompact(value: number): string {
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1).replace(/\.0$/, "")} mln`;
  if (Math.abs(value) >= 1000) return `${(value / 1000).toFixed(1).replace(/\.0$/, "")}K`;
  return String(value);
}

export function formatMoney(value: string | number, currency = "UZS"): string {
  const n = typeof value === "string" ? Number(value) : value;
  const label = currency === "UZS" ? "so'm" : currency;
  return `${formatNumber(Math.round(n))} ${label}`;
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 60) return `${Math.round(seconds)} s`;
  if (seconds < 3600) {
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return s ? `${m} daq ${s} s` : `${m} daq`;
  }
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return m ? `${h} soat ${m} daq` : `${h} soat`;
}

export function formatKpiValue(value: number | null, unit: string): string {
  if (value === null || value === undefined) return "—";
  if (unit === "percent") return `${value.toFixed(1).replace(/\.0$/, "")}%`;
  if (unit === "seconds") return formatDuration(value);
  return formatNumber(value);
}

export function addDays(key: string, days: number): string {
  const [y, m, d] = key.split("-").map(Number);
  const date = new Date(Date.UTC(y, m - 1, d + days));
  return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}`;
}

export function weekdayOfKey(key: string): number {
  const [y, m, d] = key.split("-").map(Number);
  return (new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7;
}

export function daysBetween(a: string, b: string): number {
  const [y1, m1, d1] = a.split("-").map(Number);
  const [y2, m2, d2] = b.split("-").map(Number);
  return Math.round((Date.UTC(y2, m2 - 1, d2) - Date.UTC(y1, m1 - 1, d1)) / 86400000);
}

export function toLocalInputValue(iso: string): string {
  const p = zoned(iso);
  return `${p.year}-${pad(p.month)}-${pad(p.day)}T${pad(p.hour)}:${pad(p.minute)}`;
}

export function bytesLabel(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function formatPhone(phone: string | null | undefined): string {
  if (!phone) return "";
  const d = phone.replace(/\D/g, "");
  if (d.length === 12 && d.startsWith("998")) return `+998 ${d.slice(3, 5)} ${d.slice(5, 8)} ${d.slice(8, 10)} ${d.slice(10)}`;
  return phone;
}
