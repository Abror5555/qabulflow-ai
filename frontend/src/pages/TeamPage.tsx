import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck, UserPlus } from "lucide-react";
import { useState } from "react";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, PageHeader } from "../components/ui/Card";
import { Checkbox, Input, Select } from "../components/ui/Form";
import { ConfirmDialog, Dialog } from "../components/ui/Overlay";
import { Avatar } from "../components/ui/Misc";
import { EmptyState, ErrorState, Skeleton } from "../components/ui/States";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { ApiError, errorMessage, get, patch, post } from "../lib/api";
import { ROLES } from "../lib/constants";
import { formatDateTime } from "../lib/format";
import { useBranches } from "../lib/queries";
import type { Member, Paginated } from "../lib/types";

const ROLE_INFO = [
  { role: "Egasi", text: "Hamma narsa: jamoa, integratsiyalar, sozlamalar, eksport." },
  { role: "Menejer", text: "Kurslar, bilim bazasi, AI sozlamalari, analitika, o'qishga yozilishni tasdiqlash." },
  { role: "Operator", text: "Mijozlar, suhbatlar va sinov darslari (filial cheklovi bilan)." },
];

function InviteDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const { data: branches } = useBranches();
  const [form, setForm] = useState({ full_name: "", email: "", role: "operator", password: "", branch_ids: [] as number[] });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const mutation = useMutation({
    mutationFn: () => post<Member>("/team/invite/", form),
    onSuccess: (m) => {
      toast.success("Xodim qo'shildi", `${m.full_name} — boshlang'ich parolni xavfsiz yo'l bilan yetkazing.`);
      void qc.invalidateQueries({ queryKey: ["team"] });
      setForm({ full_name: "", email: "", role: "operator", password: "", branch_ids: [] });
      onClose();
    },
    onError: (e) => {
      if (e instanceof ApiError) setErrors(Object.fromEntries(Object.keys(e.fields).map((k) => [k, e.fieldError(k) ?? ""])));
      toast.error("Qo'shilmadi", errorMessage(e));
    },
  });
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Xodim qo'shish"
      footer={
        <>
          <Button onClick={onClose}>Bekor qilish</Button>
          <Button variant="primary" loading={mutation.isPending} onClick={() => mutation.mutate()}>
            Qo'shish
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Input label="To'liq ism" required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} error={errors.full_name} data-autofocus />
        <Input label="Email" type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} error={errors.email} />
        <Select label="Rol" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} options={ROLES} />
        <Input label="Boshlang'ich parol" type="password" required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} error={errors.password} hint="Kamida 8 belgi" autoComplete="new-password" />
        <fieldset className="sm:col-span-2">
          <legend className="mb-1.5 text-[13px] font-medium text-ink-2">Filiallarga kirish (bo'sh — barchasi)</legend>
          <div className="flex flex-wrap gap-4">
            {branches?.map((b) => (
              <Checkbox key={b.id} label={b.name} checked={form.branch_ids.includes(b.id)} onChange={(c) => setForm({ ...form, branch_ids: c ? [...form.branch_ids, b.id] : form.branch_ids.filter((x) => x !== b.id) })} />
            ))}
          </div>
        </fieldset>
      </div>
    </Dialog>
  );
}

export default function TeamPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const { can, me } = useAuth();
  const isOwner = can("owner");
  const { data: branches } = useBranches();
  const [inviteOpen, setInviteOpen] = useState(false);
  const [deactivate, setDeactivate] = useState<Member | null>(null);
  const query = useQuery({ queryKey: ["team", "list"], queryFn: () => get<Paginated<Member>>("/team/", { page_size: 100 }) });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<Member> }) => patch<Member>(`/team/${id}/`, body),
    onSuccess: () => { toast.success("Saqlandi"); setDeactivate(null); void qc.invalidateQueries({ queryKey: ["team"] }); },
    onError: (e) => toast.error("Saqlanmadi", errorMessage(e)),
  });
  return (
    <>
      <PageHeader
        title="Jamoa"
        subtitle="Xodimlar, rollar va filial bo'yicha kirish huquqlari"
        actions={isOwner && <Button variant="primary" icon={<UserPlus className="size-4" />} onClick={() => setInviteOpen(true)}>Xodim qo'shish</Button>}
      />
      <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-3">
        {ROLE_INFO.map((r) => (
          <Card key={r.role} className="p-4">
            <p className="flex items-center gap-2 text-sm font-semibold text-ink"><ShieldCheck className="size-4 text-accent" aria-hidden /> {r.role}</p>
            <p className="mt-1 text-[13px] text-ink-3">{r.text}</p>
          </Card>
        ))}
      </div>
      <Card className="overflow-hidden">
        {query.isError ? <ErrorState error={query.error} onRetry={() => query.refetch()} /> : query.isLoading ? <Skeleton className="m-4 h-56" /> : query.data!.results.length === 0 ? <EmptyState title="Xodimlar yo'q" /> : (
          <>
          <ul className="divide-y divide-line md:hidden">
            {query.data!.results.map((m) => {
              const self = m.user_id === me?.id;
              return (
                <li key={m.id} className="space-y-2.5 p-4">
                  <div className="flex items-center gap-2.5">
                    <Avatar initials={m.initials} name={m.full_name} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium text-ink">{m.full_name}{self && <span className="ml-1.5 text-[12px] font-normal text-ink-3">(siz)</span>}</p>
                      <p className="truncate text-[12px] text-ink-3">{m.email}</p>
                    </div>
                    <Badge tone={m.is_active ? "success" : "neutral"} dot>{m.is_active ? "Faol" : "O'chirilgan"}</Badge>
                  </div>
                  {isOwner && !self ? (
                    <div className="flex items-center gap-2">
                      <Select aria-label={`${m.full_name} roli`} className="h-8 text-[13px]" value={m.role} onChange={(e) => update.mutate({ id: m.id, body: { role: e.target.value as Member["role"] } })} options={ROLES} />
                      {m.is_active ? (
                        <Button size="sm" variant="dangerGhost" onClick={() => setDeactivate(m)}>O'chirish</Button>
                      ) : (
                        <Button size="sm" variant="ghost" onClick={() => update.mutate({ id: m.id, body: { is_active: true } })}>Faollashtirish</Button>
                      )}
                    </div>
                  ) : (
                    <Badge tone={m.role === "owner" ? "accent" : m.role === "manager" ? "teal" : "neutral"}>{ROLES.find((r) => r.value === m.role)?.label}</Badge>
                  )}
                  <p className="text-[12px] text-ink-3">Filiallar: {m.branch_ids.length ? branches?.filter((b) => m.branch_ids.includes(b.id)).map((b) => b.name).join(", ") : "barchasi"}</p>
                </li>
              );
            })}
          </ul>
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="border-b border-line bg-surface-2 text-left text-[12px] text-ink-3">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Xodim</th>
                  <th className="px-3 py-2.5 font-medium">Rol</th>
                  <th className="px-3 py-2.5 font-medium">Filiallar</th>
                  <th className="px-3 py-2.5 font-medium">Oxirgi kirish</th>
                  <th className="px-3 py-2.5 font-medium">Holat</th>
                  {isOwner && <th className="px-4 py-2.5 text-right font-medium">Amal</th>}
                </tr>
              </thead>
              <tbody>
                {query.data!.results.map((m) => {
                  const self = m.user_id === me?.id;
                  return (
                    <tr key={m.id} className="border-b border-line last:border-0">
                      <td className="px-4 py-3">
                        <span className="flex items-center gap-2.5">
                          <Avatar initials={m.initials} name={m.full_name} />
                          <span>
                            <span className="block font-medium text-ink">{m.full_name}{self && <span className="ml-1.5 text-[12px] font-normal text-ink-3">(siz)</span>}</span>
                            <span className="block text-[12px] text-ink-3">{m.email}</span>
                          </span>
                        </span>
                      </td>
                      <td className="px-3 py-3">
                        {isOwner && !self ? (
                          <Select aria-label={`${m.full_name} roli`} className="h-8 w-[140px] text-[13px]" value={m.role} onChange={(e) => update.mutate({ id: m.id, body: { role: e.target.value as Member["role"] } })} options={ROLES} />
                        ) : (
                          <Badge tone={m.role === "owner" ? "accent" : m.role === "manager" ? "teal" : "neutral"}>{ROLES.find((r) => r.value === m.role)?.label}</Badge>
                        )}
                      </td>
                      <td className="px-3 py-3">
                        {isOwner && m.role !== "owner" ? (
                          <div className="flex flex-wrap gap-3">
                            {branches?.map((b) => (
                              <Checkbox key={b.id} label={b.name.replace(" filiali", "")} checked={m.branch_ids.includes(b.id)} onChange={(c) => update.mutate({ id: m.id, body: { branch_ids: c ? [...m.branch_ids, b.id] : m.branch_ids.filter((x) => x !== b.id) } })} />
                            ))}
                          </div>
                        ) : (
                          <span className="text-[13px] text-ink-2">{m.branch_ids.length ? branches?.filter((b) => m.branch_ids.includes(b.id)).map((b) => b.name).join(", ") : "Barcha filiallar"}</span>
                        )}
                      </td>
                      <td className="px-3 py-3 text-[13px] text-ink-3">{formatDateTime(m.last_login)}</td>
                      <td className="px-3 py-3"><Badge tone={m.is_active ? "success" : "neutral"} dot>{m.is_active ? "Faol" : "O'chirilgan"}</Badge></td>
                      {isOwner && (
                        <td className="px-4 py-3 text-right">
                          {!self && (m.is_active ? (
                            <Button size="sm" variant="dangerGhost" onClick={() => setDeactivate(m)}>O'chirish</Button>
                          ) : (
                            <Button size="sm" variant="ghost" onClick={() => update.mutate({ id: m.id, body: { is_active: true } })}>Faollashtirish</Button>
                          ))}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          </>
        )}
      </Card>
      {!isOwner && <p className="mt-3 text-[13px] text-ink-3">Jamoani faqat tashkilot egasi o'zgartira oladi.</p>}
      <InviteDialog open={inviteOpen} onClose={() => setInviteOpen(false)} />
      <ConfirmDialog open={!!deactivate} onClose={() => setDeactivate(null)} onConfirm={() => deactivate && update.mutate({ id: deactivate.id, body: { is_active: false } })} loading={update.isPending} danger title="Xodimni o'chirasizmi?" body={<>{deactivate?.full_name} tizimga kira olmaydi. Uning tarixi va biriktirilgan yozuvlari saqlanadi.</>} confirmLabel="O'chirish" />
    </>
  );
}
