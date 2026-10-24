import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, FileText, Lock, RefreshCw, Search, ShieldAlert, Trash2, UploadCloud, Users } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, CardHeader, PageHeader } from "../components/ui/Card";
import { Input, Select } from "../components/ui/Form";
import { ConfirmDialog, Drawer } from "../components/ui/Overlay";
import { Segmented } from "../components/ui/Misc";
import { EmptyState, ErrorState, Skeleton, Spinner } from "../components/ui/States";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { api, del, errorMessage, get, patch, post } from "../lib/api";
import { cn } from "../lib/cn";
import type { Tone } from "../lib/constants";
import { bytesLabel, formatDateTime } from "../lib/format";
import type { KnowledgeDoc, Paginated } from "../lib/types";

const STATUS_TONE: Record<string, Tone> = { pending: "neutral", processing: "info", indexed: "success", no_text: "warning", failed: "danger" };

function Uploader() {
  const qc = useQueryClient();
  const toast = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [visibility, setVisibility] = useState<"customer" | "internal">("customer");
  const [drag, setDrag] = useState(false);
  const upload = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("visibility", visibility);
      return api<KnowledgeDoc>("/knowledge/documents/", { method: "POST", body: fd });
    },
    onSuccess: (d) => { toast.success("Hujjat yuklandi", `${d.title} — qayta ishlanmoqda`); void qc.invalidateQueries({ queryKey: ["knowledge"] }); },
    onError: (e) => toast.error("Yuklanmadi", errorMessage(e)),
  });
  const handleFiles = (files: FileList | null) => {
    if (!files) return;
    Array.from(files).forEach((f) => upload.mutate(f));
  };
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDrag(false);
    handleFiles(e.dataTransfer.files);
  };
  return (
    <Card className="p-4">
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
        className={cn("flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-8 text-center transition-colors", drag ? "border-accent bg-accent-soft" : "border-line-strong bg-surface-2")}
      >
        <span className="mb-3 flex size-11 items-center justify-center rounded-xl bg-surface text-accent shadow-card">
          {upload.isPending ? <Spinner /> : <UploadCloud className="size-5" aria-hidden />}
        </span>
        <p className="font-medium text-ink">Faylni shu yerga tashlang yoki tanlang</p>
        <p className="mt-1 text-[13px] text-ink-3">PDF, TXT yoki Markdown · maksimal 10 MB · skaner PDF matnsiz bo'lsa indekslanmaydi</p>
        <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
          <Segmented
            label="Ko'rinish darajasi"
            value={visibility}
            onChange={setVisibility}
            items={[
              { value: "customer", label: "Mijozlar uchun", icon: <Users className="size-3.5" /> },
              { value: "internal", label: "Faqat xodimlar", icon: <Lock className="size-3.5" /> },
            ]}
          />
          <Button variant="primary" onClick={() => inputRef.current?.click()} loading={upload.isPending}>
            Fayl tanlash
          </Button>
          <input ref={inputRef} type="file" accept=".pdf,.txt,.md,.markdown,application/pdf,text/plain,text/markdown" multiple className="sr-only" onChange={(e) => { handleFiles(e.target.files); e.target.value = ""; }} aria-label="Bilim bazasi fayli" />
        </div>
      </div>
    </Card>
  );
}

function SearchTester() {
  const [q, setQ] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [audience, setAudience] = useState<"customer" | "staff">("customer");
  const query = useQuery({
    queryKey: ["knowledge", "search", submitted, audience],
    queryFn: () => get<{ results: { chunk_id: number; document_title: string; page_number: number | null; visibility: string; snippet: string; score: number }[] }>("/knowledge/search/", { q: submitted, audience }),
    enabled: submitted.length >= 2,
  });
  return (
    <Card>
      <CardHeader title="Qidiruvni sinash" subtitle="AI aynan shu qidiruv natijalaridan manba bilan javob beradi" icon={<Search className="size-4" />} />
      <div className="space-y-3 px-5 pb-5">
        <form className="flex flex-col gap-2" onSubmit={(e) => { e.preventDefault(); setSubmitted(q.trim()); }}>
          <Input aria-label="Qidiruv so'rovi" placeholder="Masalan: oilaviy chegirma" value={q} onChange={(e) => setQ(e.target.value)} />
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Segmented label="Kim uchun" value={audience} onChange={setAudience} items={[{ value: "customer", label: "Mijoz ko'radi" }, { value: "staff", label: "Xodim ko'radi" }]} />
            <Button type="submit" variant="primary" icon={<Search className="size-4" />}>Qidirish</Button>
          </div>
        </form>
        {query.isFetching && <Skeleton className="h-20" />}
        {query.data && query.data.results.length === 0 && <p className="text-[13px] text-ink-3">Mos bo'lak topilmadi — AI aniqlashtiradi yoki administratorga o'tkazadi.</p>}
        <ul className="space-y-2">
          {query.data?.results.map((r) => (
            <li key={r.chunk_id} className="rounded-lg border border-line p-3">
              <div className="mb-1 flex flex-wrap items-center gap-2 text-[12px] text-ink-3">
                <FileText className="size-3.5" aria-hidden />
                <span className="font-medium text-ink-2">{r.document_title}</span>
                {r.page_number && <span>{r.page_number}-bet</span>}
                <Badge tone={r.visibility === "customer" ? "teal" : "neutral"}>{r.visibility === "customer" ? "Mijozlar" : "Ichki"}</Badge>
                <span className="ml-auto tabular">moslik {r.score}</span>
              </div>
              <p className="text-[13px] whitespace-pre-wrap text-ink">{r.snippet}</p>
            </li>
          ))}
        </ul>
      </div>
    </Card>
  );
}

export default function KnowledgePage() {
  const qc = useQueryClient();
  const toast = useToast();
  const { can } = useAuth();
  const editable = can("manager");
  const [preview, setPreview] = useState<number | null>(null);
  const [toDelete, setToDelete] = useState<KnowledgeDoc | null>(null);
  const docs = useQuery({
    queryKey: ["knowledge", "docs"],
    queryFn: () => get<Paginated<KnowledgeDoc>>("/knowledge/documents/", { page_size: 100 }),
    refetchInterval: (q) => (q.state.data?.results.some((d) => d.status === "pending" || d.status === "processing") ? 2000 : false),
  });
  const chunks = useQuery({
    queryKey: ["knowledge", "chunks", preview],
    queryFn: () => get<{ document: KnowledgeDoc; chunks: { id: number; position: number; page_number: number | null; text: string }[] }>(`/knowledge/documents/${preview}/chunks/`),
    enabled: !!preview,
  });
  const reprocess = useMutation({
    mutationFn: (id: number) => post(`/knowledge/documents/${id}/reprocess/`),
    onSuccess: () => { toast.success("Qayta indekslash boshlandi"); void qc.invalidateQueries({ queryKey: ["knowledge"] }); },
    onError: (e) => toast.error("Bajarilmadi", errorMessage(e)),
  });
  const visibility = useMutation({
    mutationFn: ({ id, v }: { id: number; v: string }) => patch(`/knowledge/documents/${id}/`, { visibility: v }),
    onSuccess: () => { toast.success("Ko'rinish darajasi o'zgardi"); void qc.invalidateQueries({ queryKey: ["knowledge"] }); },
    onError: (e) => toast.error("O'zgarmadi", errorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: (id: number) => del(`/knowledge/documents/${id}/`),
    onSuccess: () => { toast.success("Hujjat o'chirildi"); setToDelete(null); void qc.invalidateQueries({ queryKey: ["knowledge"] }); },
    onError: (e) => toast.error("O'chirilmadi", errorMessage(e)),
  });

  return (
    <>
      <PageHeader title="Bilim bazasi" subtitle="FAQ, qoidalar va chegirma shartlari. Faqat «Mijozlar uchun» hujjatlar mijoz suhbatida ishlatiladi." />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
        <div className="space-y-4">
          {editable && <Uploader />}
          <Card>
            <CardHeader title="Hujjatlar" subtitle={`${docs.data?.count ?? 0} ta hujjat`} />
            <div className="px-5 pb-5">
              {docs.isError ? <ErrorState error={docs.error} onRetry={() => docs.refetch()} /> : docs.isLoading ? <Skeleton className="h-48" /> : docs.data!.results.length === 0 ? (
                <EmptyState title="Hujjat yuklanmagan" body="Markaz qoidalari va FAQ'ni yuklang — AI ulardan manba bilan javob beradi." />
              ) : (
                <ul className="divide-y divide-line">
                  {docs.data!.results.map((d) => (
                    <li key={d.id} className="flex flex-col gap-3 py-3 sm:flex-row sm:items-center">
                      <div className="flex min-w-0 flex-1 items-start gap-3">
                        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-line bg-surface-2 text-[11px] font-bold text-ink-3 uppercase">{d.file_type}</span>
                        <div className="min-w-0">
                          <p className="truncate font-medium text-ink">{d.title}</p>
                          <p className="text-[12px] text-ink-3">
                            {d.original_filename} · {bytesLabel(d.size_bytes)} · {d.chunk_count} bo'lak{d.page_count ? ` · ${d.page_count} bet` : ""} · {formatDateTime(d.created_at)}
                          </p>
                          {d.status_message && <p className="mt-0.5 text-[12px] text-warning">{d.status_message}</p>}
                          {d.flagged_lines > 0 && (
                            <p className="mt-0.5 inline-flex items-center gap-1 text-[12px] text-ink-3">
                              <ShieldAlert className="size-3.5" aria-hidden /> {d.flagged_lines} ta ko'rsatmaga o'xshash qator mijozga chiqarilmaydi
                            </p>
                          )}
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-2 sm:justify-end">
                        <Badge tone={STATUS_TONE[d.status]} dot>{d.status === "processing" || d.status === "pending" ? <span className="inline-flex items-center gap-1">{d.status_label}<Spinner className="[&_svg]:size-3" /></span> : d.status_label}</Badge>
                        {editable ? (
                          <Select aria-label={`${d.title} ko'rinish darajasi`} className="h-8 w-[150px] text-[13px]" value={d.visibility} onChange={(e) => visibility.mutate({ id: d.id, v: e.target.value })} options={[{ value: "customer", label: "Mijozlar uchun" }, { value: "internal", label: "Faqat xodimlar" }]} />
                        ) : (
                          <Badge tone={d.visibility === "customer" ? "teal" : "neutral"}>{d.visibility_label}</Badge>
                        )}
                        <Button size="icon-sm" variant="ghost" onClick={() => setPreview(d.id)} aria-label={`${d.title} — ko'rish`}><Eye className="size-4" /></Button>
                        {editable && (
                          <>
                            <Button size="icon-sm" variant="ghost" onClick={() => reprocess.mutate(d.id)} aria-label={`${d.title} — qayta indekslash`}><RefreshCw className="size-4" /></Button>
                            <Button size="icon-sm" variant="dangerGhost" onClick={() => setToDelete(d)} aria-label={`${d.title} — o'chirish`}><Trash2 className="size-4" /></Button>
                          </>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Card>
        </div>
        <SearchTester />
      </div>
      <Drawer open={!!preview} onClose={() => setPreview(null)} width="lg" title={chunks.data?.document.title ?? "Hujjat"} subtitle={chunks.data && `${chunks.data.document.visibility_label} · ${chunks.data.chunks.length} bo'lak`} headerExtra={preview ? <a className="text-[13px] font-medium text-accent hover:underline" href={`/api/knowledge/documents/${preview}/download/`}>Yuklab olish</a> : null}>
        {chunks.isLoading && <Skeleton className="h-64" />}
        {chunks.data?.chunks.length === 0 && <EmptyState title="Indekslangan bo'lak yo'q" body={chunks.data.document.status_message} />}
        <ol className="space-y-3">
          {chunks.data?.chunks.map((c) => (
            <li key={c.id} className="rounded-lg border border-line p-3">
              <p className="mb-1 text-[11px] font-medium text-ink-3">#{c.position + 1}{c.page_number ? ` · ${c.page_number}-bet` : ""}</p>
              <p className="text-[13px] whitespace-pre-wrap text-ink">{c.text}</p>
            </li>
          ))}
        </ol>
      </Drawer>
      <ConfirmDialog open={!!toDelete} onClose={() => setToDelete(null)} onConfirm={() => toDelete && remove.mutate(toDelete.id)} loading={remove.isPending} danger title="Hujjatni o'chirasizmi?" body={<>«{toDelete?.title}» va uning barcha indekslangan bo'laklari o'chiriladi. AI endi bu manbadan foydalanmaydi.</>} confirmLabel="O'chirish" />
    </>
  );
}
