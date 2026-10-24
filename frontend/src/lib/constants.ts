import type { LeadStatus } from "./types";

export const LEAD_STATUSES: { value: LeadStatus; label: string; tone: Tone }[] = [
  { value: "new", label: "Yangi", tone: "info" },
  { value: "qualified", label: "Ehtiyoj aniqlandi", tone: "accent" },
  { value: "trial_booked", label: "Sinovga yozildi", tone: "teal" },
  { value: "trial_attended", label: "Sinovga keldi", tone: "success" },
  { value: "enrolled", label: "O'qishga yozildi", tone: "successStrong" },
  { value: "lost", label: "Yo'qotilgan", tone: "neutral" },
];

export const LEAD_SOURCES = [
  { value: "telegram", label: "Telegram" },
  { value: "webchat", label: "Veb-chat" },
  { value: "manual", label: "Qo'lda" },
  { value: "referral", label: "Tavsiya" },
  { value: "walk_in", label: "Tashrif" },
];

export const BOOKING_STATUSES = [
  { value: "confirmed", label: "Tasdiqlangan", tone: "accent" as Tone },
  { value: "attended", label: "Qatnashdi", tone: "success" as Tone },
  { value: "no_show", label: "Kelmadi", tone: "warning" as Tone },
  { value: "cancelled", label: "Bekor qilingan", tone: "danger" as Tone },
];

export const ROLES = [
  { value: "owner", label: "Egasi" },
  { value: "manager", label: "Menejer" },
  { value: "operator", label: "Operator" },
];

export const LANGUAGES = [
  { value: "uz", label: "O'zbekcha" },
  { value: "ru", label: "Русский" },
  { value: "en", label: "English" },
];

export type Tone = "neutral" | "info" | "accent" | "teal" | "success" | "successStrong" | "warning" | "danger";

export function leadStatusTone(status: string): Tone {
  return LEAD_STATUSES.find((s) => s.value === status)?.tone ?? "neutral";
}

export function bookingStatusTone(status: string): Tone {
  return BOOKING_STATUSES.find((s) => s.value === status)?.tone ?? "neutral";
}

export const ROLE_LEVEL: Record<string, number> = { operator: 1, manager: 2, owner: 3 };
