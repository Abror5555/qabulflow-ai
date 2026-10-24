export type Role = "owner" | "manager" | "operator";

export interface Me {
  id: number;
  email: string;
  full_name: string;
  initials: string;
  preferences: { theme?: "light" | "dark" | "system"; leads_view?: string; calendar_view?: string };
  is_demo_user: boolean;
  role: Role | null;
  branch_ids: number[];
  organization: { id: number; name: string; slug: string; timezone: string; default_language: string; currency: string; is_demo: boolean } | null;
  organizations: { id: number; name: string; role: Role }[];
  demo_mode: boolean;
  notification_prefs: Record<string, boolean>;
}

export interface Paginated<T> {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface UserBrief {
  id: number;
  full_name: string;
  initials: string;
}

export type LeadStatus = "new" | "qualified" | "trial_booked" | "trial_attended" | "enrolled" | "lost";

export interface Lead {
  id: number;
  display_name: string;
  full_name: string;
  phone: string;
  phone_verified: boolean;
  telegram_username: string;
  language: string;
  source: string;
  source_label: string;
  status: LeadStatus;
  status_label: string;
  branch_id: number | null;
  branch_name: string | null;
  interested_course_id: number | null;
  interested_course_name: string | null;
  goal: string;
  level: string;
  preferred_time: string;
  assigned_to: UserBrief | null;
  consent_reminders: boolean;
  created_at: string;
  last_activity_at: string;
}

export interface LeadDetail extends Lead {
  notes: { id: number; text: string; author: UserBrief | null; created_at: string }[];
  status_history: { id: number; from_status: string; from_label: string; to_status: string; to_label: string; changed_by: UserBrief | null; changed_via: string; reason: string; created_at: string }[];
  bookings: { id: number; status: string; status_label: string; course_name: string; branch_name: string; starts_at: string; channel: string; confirmed_at: string; cancelled_at: string | null }[];
  enrollments: Enrollment[];
  conversations: { id: number; channel: string; mode: string; last_message_at: string; preview: string }[];
  telegram_user_id: number | null;
  consent_at: string | null;
}

export interface Enrollment {
  id: number;
  lead_id: number;
  lead_name: string;
  course_id: number;
  course_name: string;
  group_id: number | null;
  group_name: string | null;
  status: string;
  status_label: string;
  confirmed_by: UserBrief | null;
  confirmed_at: string | null;
  notes: string;
  created_at: string;
}

export interface Branch {
  id: number;
  name: string;
  address: string;
  landmark: string;
  phone: string;
  is_active: boolean;
  groups_count?: number;
}

export interface Course {
  id: number;
  name: string;
  description: string;
  level: string;
  level_label: string;
  teaching_language: string;
  price: string;
  currency: string;
  price_period: "month" | "course";
  duration_months: number;
  lessons_per_week: number;
  lesson_minutes: number;
  keywords: string[];
  is_active: boolean;
  groups_count?: number;
  upcoming_slots?: number;
}

export interface Group {
  id: number;
  name: string;
  course_id: number;
  course_name: string;
  branch_id: number;
  branch_name: string;
  teacher_name: string;
  days: number[];
  start_time: string;
  end_time: string;
  schedule_label: string;
  capacity: number;
  enrolled_count: number;
  start_date: string | null;
  is_active: boolean;
}

export interface TrialSlot {
  id: number;
  group_id: number;
  group_name: string;
  course_id: number;
  course_name: string;
  branch_id: number;
  branch_name: string;
  starts_at: string;
  ends_at: string;
  capacity: number;
  seats_taken: number;
  seats_left: number;
  status: "open" | "cancelled";
  notes: string;
  is_past: boolean;
  bookings?: { id: number; lead_id: number; lead_name: string; status: string; channel: string }[];
}

export interface Booking {
  id: number;
  lead_id: number;
  lead_name: string;
  lead_phone: string;
  slot_id: number;
  starts_at: string;
  ends_at: string;
  course_id: number;
  course_name: string;
  group_name: string;
  branch_id: number;
  branch_name: string;
  status: "confirmed" | "cancelled" | "attended" | "no_show";
  status_label: string;
  channel: string;
  channel_label: string;
  conversation_id: number | null;
  confirmed_at: string;
  cancelled_at: string | null;
  cancel_reason: string;
  attendance_marked_at: string | null;
  reschedule_count: number;
  created_by_name: string | null;
  notes: string;
  can_mark_attendance: boolean;
  events?: { id: number; event_type: string; label: string; actor_type: string; actor_name: string | null; reason: string; occurred_at: string }[];
}

export interface Message {
  id: number;
  sender: "customer" | "ai" | "operator" | "system";
  author: UserBrief | null;
  kind: "text" | "voice" | "event";
  text: string;
  language: string;
  transcript_status: string;
  transcript_confidence: number | null;
  is_demo: boolean;
  ai_status: string;
  sources: { chunk_id: number; document_id: number; document_title: string; page: number | null }[];
  tool_trace: { tool: string; ok: boolean; status: string }[];
  delivery_status: string;
  attachments: { id: number; kind: string; content_type: string; size_bytes: number; duration_seconds: number | null; download_url: string }[];
  created_at: string;
}

export interface ConversationItem {
  id: number;
  lead_id: number;
  lead_name: string;
  lead_status: LeadStatus;
  lead_status_label: string;
  channel: "telegram" | "webchat";
  channel_label: string;
  status: "open" | "closed";
  mode: "ai" | "human";
  assigned_to: UserBrief | null;
  language: string;
  needs_attention: boolean;
  last_message_at: string;
  last_message_preview: string;
  unanswered: boolean;
  created_at: string;
}

export interface ConversationDetail extends ConversationItem {
  handoffs: { id: number; requested_via: string; reason: string; status: string; taken_by: UserBrief | null; taken_at: string | null; created_at: string }[];
  lead: {
    id: number;
    display_name: string;
    full_name: string;
    phone: string;
    telegram_username: string;
    source: string;
    source_label: string;
    status: LeadStatus;
    status_label: string;
    language: string;
    goal: string;
    level: string;
    preferred_time: string;
    branch_name: string | null;
    interested_course_id: number | null;
    interested_course_name: string | null;
    consent_reminders: boolean;
    bookings: { id: number; status: string; status_label: string; course_name: string; branch_name: string; starts_at: string }[];
  };
  state_summary: { stage: string | null; pending_booking: boolean; course_id: number | null };
}

export interface KpiPoint {
  bucket: string;
  value: number | null;
}

export interface Kpi {
  key: string;
  label: string;
  value: number | null;
  previous: number | null;
  change: number | null;
  change_unit: "percent" | "pp";
  no_previous_data: boolean;
  unit: "count" | "percent" | "seconds";
  lower_is_better: boolean;
  sparkline: KpiPoint[];
  numerator?: number;
  denominator?: number;
  definition?: string;
  samples?: number;
}

export interface Overview {
  filters: { date_from: string; date_to: string; branch_id: number | null; course_id: number | null; source: string | null; granularity: "day" | "week" };
  period: { start: string; end: string; previous_from: string; previous_to: string; timezone: string };
  kpis: Kpi[];
  timeseries: { bucket: string; bucket_start: string; bucket_end: string; new_leads: number; confirmed_bookings: number; cancelled_bookings: number }[];
  channels: { channel: string; label: string; count: number }[];
  sources: { source: string; label: string; count: number }[];
  courses: { course_id: number; name: string; interest: number; bookings: number }[];
  funnel: { stage: string; label: string; count: number; rate: number | null }[];
  booking_statuses: { status: string; label: string; count: number }[];
  upcoming_bookings: { booking_id: number; lead_id: number; lead_name: string; course: string; branch: string; starts_at: string; channel: string }[];
  recent_activity: { id: number; action: string; summary: string; actor_type: string; actor_name: string | null; created_at: string }[];
  has_data: boolean;
}

export interface KnowledgeDoc {
  id: number;
  title: string;
  file_type: string;
  original_filename: string;
  size_bytes: number;
  visibility: "customer" | "internal";
  visibility_label: string;
  status: "pending" | "processing" | "indexed" | "no_text" | "failed";
  status_label: string;
  status_message: string;
  page_count: number;
  chunk_count: number;
  char_count: number;
  flagged_lines: number;
  uploaded_by_name: string | null;
  indexed_at: string | null;
  created_at: string;
}

export interface Member {
  id: number;
  user_id: number;
  full_name: string;
  email: string;
  initials: string;
  role: Role;
  branch_ids: number[];
  is_active: boolean;
  last_login: string | null;
  created_at: string;
}

export interface NotificationItem {
  id: number;
  kind: string;
  title: string;
  body: string;
  link: string;
  is_read: boolean;
  created_at: string;
}

export interface AISettings {
  is_enabled: boolean;
  greetings: Record<string, string>;
  enabled_languages: string[];
  tone: "friendly" | "formal";
  working_hours: { start: string; end: string; days: number[] };
  handoff_keywords: string[];
  handoff_after_failed_attempts: number;
  handoff_outside_hours_notice: boolean;
  ask_phone_before_booking: boolean;
  max_slots_to_offer: number;
  reminder_hours_before: number;
  provider: { name: string; model: string; is_demo: boolean };
  updated_at: string;
}

export interface IntegrationItem {
  kind: "telegram" | "ai" | "stt";
  state: "not_configured" | "demo" | "configured" | "connected" | "error";
  note: string;
  provider?: string;
  model?: string;
  mode?: string;
  token_configured?: boolean;
  bot_username?: string | null;
  last_checked_at?: string | null;
  last_error?: string;
}

export interface WidgetSettings {
  public_key: string;
  is_enabled: boolean;
  allowed_origins: string[];
  title: string;
  accent_color: string;
  position: "right" | "left";
  embed_code: string;
  chat_url: string;
  updated_at: string;
}

export interface OutboxItem {
  id: number;
  channel: string;
  recipient_masked: string;
  text: string;
  kind: string;
  status: string;
  attempts: number;
  last_error: string;
  created_at: string;
  sent_at: string | null;
}
