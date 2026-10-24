import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bell,
  BookOpen,
  Bot,
  Building2,
  CalendarCheck,
  CalendarRange,
  ChartLine,
  Check,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  Menu as MenuIcon,
  MessagesSquare,
  Monitor,
  Moon,
  PlugZap,
  Search,
  Sun,
  Users,
  UsersRound,
  X,
} from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { useFilters, type RangePreset } from "../../contexts/FiltersContext";
import { useTheme } from "../../contexts/ThemeContext";
import { get, post } from "../../lib/api";
import { cn } from "../../lib/cn";
import { formatDayKey, formatPhone, relativeTime } from "../../lib/format";
import { useBranches } from "../../lib/queries";
import type { Lead, NotificationItem, Paginated, Role } from "../../lib/types";
import { DemoBadge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Avatar, Menu, MenuItem } from "../ui/Misc";

interface NavItem {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  role?: Role;
  badgeKey?: "waiting";
}

const NAV: NavItem[] = [
  { to: "/", label: "Umumiy ko'rinish", icon: LayoutDashboard },
  { to: "/leads", label: "Mijozlar", icon: Users },
  { to: "/conversations", label: "Suhbatlar", icon: MessagesSquare, badgeKey: "waiting" },
  { to: "/bookings", label: "Sinov darslari", icon: CalendarCheck },
  { to: "/courses", label: "Kurslar va guruhlar", icon: GraduationCap },
  { to: "/knowledge", label: "Bilim bazasi", icon: BookOpen },
  { to: "/ai", label: "AI sozlamalari", icon: Bot },
  { to: "/analytics", label: "Analitika", icon: ChartLine, role: "manager" },
  { to: "/team", label: "Jamoa", icon: UsersRound, role: "manager" },
  { to: "/settings", label: "Integratsiyalar", icon: PlugZap },
];

function Logo({ compact }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <svg viewBox="0 0 32 32" className="size-8 shrink-0" aria-hidden>
        <rect width="32" height="32" rx="9" fill="#4F46E5" />
        <path d="M9 11.5a2.5 2.5 0 0 1 2.5-2.5h9a2.5 2.5 0 0 1 2.5 2.5v6a2.5 2.5 0 0 1-2.5 2.5H15l-4 3v-3h0.5A2.5 2.5 0 0 1 9 17.5z" fill="#fff" />
        <circle cx="21.5" cy="21.5" r="4.5" fill="#14B8A6" stroke="#4F46E5" strokeWidth="1.5" />
        <path d="m19.6 21.6 1.3 1.3 2.4-2.6" stroke="#fff" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {!compact && (
        <span className="text-[15px] font-semibold tracking-[-0.01em] text-ink">
          QabulFlow <span className="text-accent">AI</span>
        </span>
      )}
    </div>
  );
}

function SidebarNav({ collapsed, onNavigate, waiting }: { collapsed?: boolean; onNavigate?: () => void; waiting: number }) {
  const { can } = useAuth();
  return (
    <nav aria-label="Asosiy menyu" className="flex flex-col gap-0.5">
      {NAV.filter((n) => !n.role || can(n.role)).map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === "/"}
          onClick={onNavigate}
          title={collapsed ? item.label : undefined}
          className={({ isActive }) =>
            cn(
              "group relative flex h-10 items-center gap-3 rounded-[10px] px-3 text-sm font-medium transition-colors",
              isActive ? "bg-accent-soft text-accent-ink" : "text-ink-2 hover:bg-surface-3 hover:text-ink",
              collapsed && "justify-center px-0",
            )
          }
        >
          <item.icon className="size-[18px] shrink-0" aria-hidden />
          {!collapsed && <span className="truncate">{item.label}</span>}
          {item.badgeKey === "waiting" && waiting > 0 && (
            <span
              className={cn("rounded-full bg-danger-strong px-1.5 text-[11px] leading-[18px] font-semibold text-white tabular", collapsed ? "absolute top-1 right-1.5" : "ml-auto")}
              aria-label={`${waiting} ta suhbat operator kutmoqda`}
            >
              {waiting}
            </span>
          )}
        </NavLink>
      ))}
    </nav>
  );
}

function OrgCard({ collapsed }: { collapsed?: boolean }) {
  const { me, switchOrg } = useAuth();
  if (!me?.organization) return null;
  const roleLabel = { owner: "Egasi", manager: "Menejer", operator: "Operator" }[me.role ?? "operator"];
  const card = (
    <div className={cn("flex items-center gap-2.5 rounded-xl border border-line bg-surface-2 p-2.5", collapsed && "justify-center p-2")}>
      <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-teal-soft text-teal-ink">
        <Building2 className="size-4" aria-hidden />
      </span>
      {!collapsed && (
        <div className="min-w-0 text-left">
          <p className="truncate text-[13px] font-semibold text-ink">{me.organization.name}</p>
          <p className="text-[12px] text-ink-3">{roleLabel}</p>
        </div>
      )}
    </div>
  );
  if (me.organizations.length < 2) return card;
  return (
    <Menu label="Tashkilotni almashtirish" align="left" trigger={(p) => <button type="button" {...p} className="w-full rounded-xl" aria-label="Tashkilotni almashtirish">{card}</button>}>
      {(close) =>
        me.organizations.map((o) => (
          <MenuItem key={o.id} onClick={() => { close(); void switchOrg(o.id); }} icon={o.id === me.organization?.id ? <Check className="size-4" /> : <span className="size-4" />}>
            {o.name}
          </MenuItem>
        ))
      }
    </Menu>
  );
}

const PRESETS: { value: Exclude<RangePreset, "custom">; label: string }[] = [
  { value: "7d", label: "7 kun" },
  { value: "30d", label: "30 kun" },
  { value: "90d", label: "90 kun" },
  { value: "month", label: "Shu oy" },
];

export function DateRangeControl({ alwaysLabel = false }: { alwaysLabel?: boolean }) {
  const { range, setRange, applyPreset } = useFilters();
  const [from, setFrom] = useState(range.from);
  const [to, setTo] = useState(range.to);
  useEffect(() => {
    setFrom(range.from);
    setTo(range.to);
  }, [range.from, range.to]);
  const label = range.preset === "custom" ? `${formatDayKey(range.from)} – ${formatDayKey(range.to)}` : PRESETS.find((p) => p.value === range.preset)?.label;
  return (
    <Menu
      label="Sana oralig'i"
      trigger={(p) => (
        <button type="button" {...p} className="inline-flex h-9 items-center gap-2 rounded-[10px] border border-line bg-surface px-3 text-[13px] font-medium text-ink shadow-card hover:border-line-strong" aria-label={`Sana oralig'i: ${label}`}>
          <CalendarRange className="size-4 text-ink-3" aria-hidden />
          <span className={alwaysLabel ? "" : "hidden sm:inline"}>{label}</span>
        </button>
      )}
    >
      {(close) => (
        <div className="w-[264px] p-1">
          <p className="px-1.5 pb-1.5 text-[12px] font-medium text-ink-3">Davr</p>
          <div className="grid grid-cols-2 gap-1">
            {PRESETS.map((p) => (
              <button
                key={p.value}
                type="button"
                onClick={() => { applyPreset(p.value); close(); }}
                className={cn("h-8 rounded-lg text-[13px] font-medium", range.preset === p.value ? "bg-accent-soft text-accent-ink" : "text-ink-2 hover:bg-surface-3")}
              >
                {p.label}
              </button>
            ))}
          </div>
          <div className="mt-3 border-t border-line pt-3">
            <p className="px-1.5 pb-1.5 text-[12px] font-medium text-ink-3">Boshqa oraliq</p>
            <div className="grid grid-cols-2 gap-2 px-1">
              <label className="text-[12px] text-ink-3">
                Dan
                <input type="date" value={from} max={to} onChange={(e) => setFrom(e.target.value)} className="mt-1 h-8 w-full rounded-lg border border-line bg-surface px-2 text-[13px] text-ink" />
              </label>
              <label className="text-[12px] text-ink-3">
                Gacha
                <input type="date" value={to} min={from} onChange={(e) => setTo(e.target.value)} className="mt-1 h-8 w-full rounded-lg border border-line bg-surface px-2 text-[13px] text-ink" />
              </label>
            </div>
            <Button className="mt-2.5 w-full" size="sm" variant="primary" disabled={!from || !to || from > to} onClick={() => { setRange({ preset: "custom", from, to }); close(); }}>
              Qo'llash
            </Button>
          </div>
        </div>
      )}
    </Menu>
  );
}

function BranchSelect({ className = "hidden md:block" }: { className?: string }) {
  const { branchId, setBranchId } = useFilters();
  const { data: branches } = useBranches();
  return (
    <label className={cn("relative", className)}>
      <span className="sr-only">Filial</span>
      <select
        value={branchId ?? ""}
        onChange={(e) => setBranchId(e.target.value ? Number(e.target.value) : null)}
        className="h-9 appearance-none rounded-[10px] border border-line bg-surface pr-8 pl-3 text-[13px] font-medium text-ink shadow-card hover:border-line-strong"
      >
        <option value="">Barcha filiallar</option>
        {branches?.map((b) => (
          <option key={b.id} value={b.id}>
            {b.name}
          </option>
        ))}
      </select>
      <Building2 className="pointer-events-none absolute top-1/2 right-2.5 size-3.5 -translate-y-1/2 text-ink-3" aria-hidden />
    </label>
  );
}

function GlobalSearch() {
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(q.trim()), 250);
    return () => window.clearTimeout(t);
  }, [q]);
  useEffect(() => {
    const onDoc = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);
  const { data, isFetching } = useQuery({
    queryKey: ["global-search", debounced],
    queryFn: () => get<Paginated<Lead>>("/leads/", { search: debounced, page_size: 6 }),
    enabled: debounced.length >= 2,
  });
  return (
    <div ref={ref} className="relative w-full max-w-[340px]">
      <label className="sr-only" htmlFor="global-search">
        Mijoz qidirish
      </label>
      <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-3" aria-hidden />
      <input
        id="global-search"
        value={q}
        onChange={(e) => { setQ(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
        placeholder="Ism yoki telefon…"
        className="h-9 w-full rounded-[10px] border border-line bg-surface-2 pr-3 pl-9 text-[13px] text-ink placeholder:text-ink-3 focus:border-accent focus:bg-surface focus:outline-none"
        autoComplete="off"
      />
      {open && debounced.length >= 2 && (
        <div className="anim-fade absolute top-full right-0 left-0 z-50 mt-1.5 rounded-xl border border-line bg-surface p-1.5 shadow-pop" role="listbox" aria-label="Qidiruv natijalari">
          {isFetching && !data && <p className="px-2.5 py-2 text-[13px] text-ink-3">Qidirilmoqda…</p>}
          {data && data.results.length === 0 && <p className="px-2.5 py-2 text-[13px] text-ink-3">Hech narsa topilmadi</p>}
          {data?.results.map((lead) => (
            <button
              key={lead.id}
              type="button"
              role="option"
              aria-selected={false}
              onClick={() => { setOpen(false); setQ(""); navigate(`/leads?lead=${lead.id}`); }}
              className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left hover:bg-surface-3"
            >
              <Avatar name={lead.display_name} size="sm" />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] font-medium text-ink">{lead.display_name}</span>
                <span className="block truncate text-[12px] text-ink-3">{formatPhone(lead.phone) || lead.source_label} · {lead.status_label}</span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function Notifications() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => get<Paginated<NotificationItem> & { unread_count: number }>("/notifications/", { page_size: 8 }),
    refetchInterval: 30_000,
  });
  const unread = data?.unread_count ?? 0;
  return (
    <Menu
      label="Bildirishnomalar"
      trigger={(p) => (
        <button type="button" {...p} className="relative inline-flex size-9 items-center justify-center rounded-[10px] border border-line bg-surface text-ink-2 shadow-card hover:text-ink" aria-label={`Bildirishnomalar${unread ? `, ${unread} ta o'qilmagan` : ""}`}>
          <Bell className="size-[18px]" aria-hidden />
          {unread > 0 && <span className="absolute -top-1 -right-1 min-w-[18px] rounded-full bg-danger-strong px-1 text-[11px] leading-[18px] font-semibold text-white tabular">{unread > 9 ? "9+" : unread}</span>}
        </button>
      )}
    >
      {(close) => (
        <div className="w-[320px] max-w-[calc(100vw-32px)]">
          <div className="flex items-center justify-between px-2 py-1.5">
            <p className="text-[13px] font-semibold text-ink">Bildirishnomalar</p>
            {unread > 0 && (
              <button type="button" className="text-[12px] font-medium text-accent hover:underline" onClick={async () => { await post("/notifications/read-all/"); void qc.invalidateQueries({ queryKey: ["notifications"] }); }}>
                Hammasi o'qildi
              </button>
            )}
          </div>
          <div className="scroll-thin max-h-[360px] overflow-y-auto">
            {!data?.results.length && <p className="px-2.5 py-6 text-center text-[13px] text-ink-3">Hozircha bildirishnoma yo'q</p>}
            {data?.results.map((n) => (
              <button
                key={n.id}
                type="button"
                onClick={async () => {
                  close();
                  if (!n.is_read) {
                    await post(`/notifications/${n.id}/read/`);
                    void qc.invalidateQueries({ queryKey: ["notifications"] });
                  }
                  if (n.link) navigate(n.link);
                }}
                className="flex w-full gap-2.5 rounded-lg px-2.5 py-2 text-left hover:bg-surface-3"
              >
                <span className={cn("mt-1.5 size-2 shrink-0 rounded-full", n.is_read ? "bg-transparent" : "bg-accent")} aria-hidden />
                <span className="min-w-0">
                  <span className="block text-[13px] font-medium text-ink">{n.title}</span>
                  <span className="block truncate text-[12px] text-ink-3">{n.body}</span>
                  <span className="block text-[11px] text-ink-3">{relativeTime(n.created_at)}</span>
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </Menu>
  );
}

function ProfileMenu() {
  const { me, logout } = useAuth();
  const { choice, setChoice } = useTheme();
  const navigate = useNavigate();
  if (!me) return null;
  const themes = [
    { value: "light" as const, label: "Yorug'", icon: Sun },
    { value: "dark" as const, label: "Qorong'i", icon: Moon },
    { value: "system" as const, label: "Tizim", icon: Monitor },
  ];
  return (
    <Menu label="Profil menyusi" trigger={(p) => <button type="button" {...p} className="rounded-full" aria-label="Profil menyusi"><Avatar initials={me.initials} name={me.full_name} /></button>}>
      {(close) => (
        <div className="w-[248px]">
          <div className="border-b border-line px-2.5 pt-1 pb-2.5">
            <p className="truncate text-[13px] font-semibold text-ink">{me.full_name}</p>
            <p className="truncate text-[12px] text-ink-3">{me.email}</p>
          </div>
          <p className="px-2.5 pt-2 pb-1 text-[12px] font-medium text-ink-3">Mavzu</p>
          <div className="grid grid-cols-3 gap-1 px-1.5 pb-2" role="radiogroup" aria-label="Mavzu">
            {themes.map((t) => (
              <button key={t.value} type="button" role="radio" aria-checked={choice === t.value} onClick={() => setChoice(t.value)} className={cn("flex flex-col items-center gap-1 rounded-lg py-2 text-[12px] font-medium", choice === t.value ? "bg-accent-soft text-accent-ink" : "text-ink-2 hover:bg-surface-3")}>
                <t.icon className="size-4" aria-hidden />
                {t.label}
              </button>
            ))}
          </div>
          <div className="border-t border-line pt-1.5">
            <MenuItem onClick={() => { close(); navigate("/settings?tab=profile"); }} icon={<UsersRound className="size-4" />}>
              Profil sozlamalari
            </MenuItem>
            <MenuItem onClick={async () => { close(); await logout(); navigate("/login"); }} icon={<LogOut className="size-4" />} danger>
              Chiqish
            </MenuItem>
          </div>
        </div>
      )}
    </Menu>
  );
}

const DATE_ROUTES = ["/"];

export function AppShell({ children }: { children: ReactNode }) {
  const { me } = useAuth();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const { data: waitingData } = useQuery({
    queryKey: ["conversations", "waiting-count"],
    queryFn: () => get<Paginated<unknown>>("/conversations/", { queue: "waiting", page_size: 1 }),
    refetchInterval: 20_000,
  });
  const waiting = waitingData?.count ?? 0;
  useEffect(() => setMobileOpen(false), [location.pathname]);
  const showDate = DATE_ROUTES.includes(location.pathname);
  const demo = me?.demo_mode || me?.organization?.is_demo;

  return (
    <div className="flex min-h-full">
      <a href="#main" className="sr-only z-[80] rounded-lg bg-accent px-3 py-2 text-white focus:not-sr-only focus:fixed focus:top-3 focus:left-3">
        Asosiy kontentga o'tish
      </a>
      {/* Desktop/tablet sidebar */}
      <div className="hidden w-[76px] shrink-0 border-r border-line bg-surface lg:block xl:w-[248px]">
      <aside className="sticky top-0 flex h-screen flex-col px-3 py-4" aria-label="Yon panel">
        <div className="mb-6 flex justify-center px-1 xl:justify-start">
          <span className="xl:hidden"><Logo compact /></span>
          <span className="hidden xl:block"><Logo /></span>
        </div>
        <div className="xl:hidden"><SidebarNav collapsed waiting={waiting} /></div>
        <div className="hidden xl:block"><SidebarNav waiting={waiting} /></div>
        <div className="mt-auto">
          <div className="xl:hidden"><OrgCard collapsed /></div>
          <div className="hidden xl:block"><OrgCard /></div>
        </div>
      </aside>
      </div>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-[55] lg:hidden" role="dialog" aria-modal="true" aria-label="Menyu">
          <div className="absolute inset-0 bg-[#0f172a]/45" onClick={() => setMobileOpen(false)} aria-hidden />
          <div className="anim-slide absolute inset-y-0 left-0 flex w-[280px] flex-col bg-surface px-3 py-4 shadow-modal">
            <div className="mb-5 flex items-center justify-between px-1">
              <Logo />
              <Button variant="ghost" size="icon-sm" onClick={() => setMobileOpen(false)} aria-label="Menyuni yopish">
                <X className="size-4" />
              </Button>
            </div>
            <SidebarNav waiting={waiting} onNavigate={() => setMobileOpen(false)} />
            <div className="mt-auto"><OrgCard /></div>
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-40 border-b border-line bg-surface/85 backdrop-blur-md">
          <div className="flex h-16 items-center gap-2.5 px-4 sm:gap-3 sm:px-6">
            <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setMobileOpen(true)} aria-label="Menyuni ochish">
              <MenuIcon className="size-5" />
            </Button>
            <div className="hidden min-w-0 flex-1 sm:block">
              <GlobalSearch />
            </div>
            <div className="flex-1 sm:hidden" />
            <div className="flex items-center gap-2">
              {demo && (
                <span className="hidden md:inline-flex">
                  <DemoBadge />
                </span>
              )}
              <BranchSelect />
              {showDate && <DateRangeControl />}
              <Notifications />
              <ProfileMenu />
            </div>
          </div>
          {demo && (
            <div className="flex items-center justify-center border-t border-line bg-[#fffbeb] py-1 md:hidden dark:bg-[#2b2110]">
              <DemoBadge className="h-5 border-0 bg-transparent" />
            </div>
          )}
          <div className="flex gap-2 px-4 pb-3 sm:hidden">
            <GlobalSearch />
            <BranchSelect className="block shrink-0" />
          </div>
        </header>
        <main id="main" className="mx-auto w-full max-w-[1480px] flex-1 px-4 py-5 sm:px-6 sm:py-6">
          {children}
        </main>
      </div>
    </div>
  );
}
