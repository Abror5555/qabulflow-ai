import { useQuery } from "@tanstack/react-query";
import { CalendarCheck, LockKeyhole, Mail, MessagesSquare, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Form";
import { useAuth } from "../contexts/AuthContext";
import { errorMessage, get } from "../lib/api";

const DEMO_ACCOUNTS = [
  { role: "Egasi", email: "owner@demo.qabulflow.local" },
  { role: "Menejer", email: "manager@demo.qabulflow.local" },
  { role: "Operator (Chilonzor)", email: "operator@demo.qabulflow.local" },
];

export default function LoginPage() {
  const { me, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const health = useQuery({ queryKey: ["health"], queryFn: () => get<{ checks: { demo_mode: boolean } }>("/health/"), retry: false });
  const demo = health.data?.checks.demo_mode;
  if (me) return <Navigate to={(location.state as { from?: string } | null)?.from || "/"} replace />;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      navigate((location.state as { from?: string } | null)?.from || "/", { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-full">
      <aside className="relative hidden w-[46%] max-w-[640px] overflow-hidden bg-[#0f172a] p-10 text-white lg:flex lg:flex-col">
        <div className="pointer-events-none absolute -top-24 -right-24 size-80 rounded-full bg-[#4f46e5] opacity-40 blur-3xl" aria-hidden />
        <div className="pointer-events-none absolute -bottom-32 -left-16 size-80 rounded-full bg-[#14b8a6] opacity-25 blur-3xl" aria-hidden />
        <div className="relative flex items-center gap-2.5">
          <img src="/favicon.svg" alt="" className="size-9" />
          <span className="text-lg font-semibold">QabulFlow <span className="text-[#a5b4fc]">AI</span></span>
        </div>
        <div className="relative mt-auto">
          <h1 className="max-w-md text-[32px] leading-tight font-semibold tracking-[-0.02em]">O'quv markazi qabuli va sinov darsiga yozilish — bitta panelda</h1>
          <ul className="mt-8 space-y-4 text-[15px] text-[#cbd5e1]">
            <li className="flex gap-3"><MessagesSquare className="size-5 shrink-0 text-[#a5b4fc]" aria-hidden /> Telegram va veb-chat murojaatlari, operatorga o'tkazish</li>
            <li className="flex gap-3"><CalendarCheck className="size-5 shrink-0 text-[#5eead4]" aria-hidden /> Bazadagi jadval va sig'im asosida tasdiqlangan bronlar</li>
            <li className="flex gap-3"><ShieldCheck className="size-5 shrink-0 text-[#a5b4fc]" aria-hidden /> Rollar, filial bo'yicha kirish va tashkilotlar izolyatsiyasi</li>
          </ul>
        </div>
      </aside>
      <main className="flex flex-1 items-center justify-center px-4 py-10">
        <div className="w-full max-w-[400px]">
          <div className="mb-8 flex items-center gap-2.5 lg:hidden">
            <img src="/favicon.svg" alt="" className="size-9" />
            <span className="text-lg font-semibold text-ink">QabulFlow <span className="text-accent">AI</span></span>
          </div>
          <h2 className="text-2xl font-semibold tracking-[-0.01em] text-ink">Tizimga kirish</h2>
          <p className="mt-1 text-sm text-ink-3">Xodim hisobingiz bilan kiring</p>
          <form className="mt-6 space-y-4" onSubmit={submit} noValidate>
            <Input label="Email" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} icon={<Mail className="size-4" />} />
            <Input label="Parol" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} icon={<LockKeyhole className="size-4" />} />
            {error && (
              <p className="rounded-lg border border-danger-strong/30 bg-danger-soft px-3 py-2 text-[13px] text-danger-strong" role="alert">
                {error}
              </p>
            )}
            <Button type="submit" variant="primary" size="lg" className="w-full" loading={loading} disabled={!email || !password}>
              Kirish
            </Button>
          </form>
          {demo && (
            <div className="mt-6 rounded-xl border border-[#fcd34d] bg-[#fffbeb] p-4 dark:border-[#78350f] dark:bg-[#2b2110]">
              <p className="text-[13px] font-semibold text-[#92400e] dark:text-[#fcd34d]">Demo muhit — sintetik ma'lumotlar</p>
              <p className="mt-0.5 text-[12px] text-[#92400e]/80 dark:text-[#fcd34d]/80">Parol hamma demo hisoblar uchun README'da. Hisobni tanlang:</p>
              <div className="mt-2.5 flex flex-col gap-1.5">
                {DEMO_ACCOUNTS.map((a) => (
                  <button key={a.email} type="button" onClick={() => setEmail(a.email)} className="flex items-center justify-between rounded-lg border border-[#fde68a] bg-white/70 px-3 py-1.5 text-left text-[12px] hover:bg-white dark:border-[#4d3a12] dark:bg-transparent">
                    <span className="font-medium text-[#78350f] dark:text-[#fde68a]">{a.role}</span>
                    <span className="font-mono text-[#92400e]/80 dark:text-[#fcd34d]/80">{a.email}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
