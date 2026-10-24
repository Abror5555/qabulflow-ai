/** Django REST API bilan ishlash: session cookie + CSRF, bir xil xato formati. */

export class ApiError extends Error {
  status: number;
  code: string;
  fields: Record<string, string[] | string>;

  constructor(status: number, code: string, message: string, fields: Record<string, string[] | string> = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.fields = fields;
  }

  fieldError(name: string): string | undefined {
    const value = this.fields?.[name];
    if (!value) return undefined;
    return Array.isArray(value) ? value.join(" ") : String(value);
  }
}

function getCookie(name: string): string | null {
  const match = document.cookie.split("; ").find((row) => row.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.split("=")[1]) : null;
}

let csrfPromise: Promise<void> | null = null;

export async function ensureCsrf(): Promise<void> {
  if (getCookie("csrftoken")) return;
  if (!csrfPromise) {
    csrfPromise = fetch("/api/auth/csrf/", { credentials: "same-origin" }).then(() => undefined);
  }
  await csrfPromise;
}

type Query = Record<string, string | number | boolean | null | undefined>;

export function buildQuery(params?: Query): string {
  if (!params) return "";
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    search.set(key, String(value));
  });
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

async function parseError(res: Response): Promise<ApiError> {
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    // JSON bo'lmagan javob
  }
  const err = (body as { error?: { code?: string; message?: string; fields?: Record<string, string[]> } } | null)?.error;
  if (err) return new ApiError(res.status, err.code || "error", err.message || "Xato yuz berdi.", err.fields || {});
  if (res.status === 403) return new ApiError(403, "permission_denied", "Bu amal uchun ruxsat yo'q.");
  if (res.status === 404) return new ApiError(404, "not_found", "Yozuv topilmadi.");
  return new ApiError(res.status, "network_error", "Server bilan bog'lanib bo'lmadi. Keyinroq urinib ko'ring.");
}

export async function api<T>(path: string, options: { method?: string; body?: unknown; query?: Query; headers?: Record<string, string>; signal?: AbortSignal } = {}): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const headers: Record<string, string> = { Accept: "application/json", ...(options.headers || {}) };
  let body: BodyInit | undefined;
  if (options.body instanceof FormData) {
    body = options.body;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }
  if (method !== "GET" && method !== "HEAD") {
    await ensureCsrf();
    const token = getCookie("csrftoken");
    if (token) headers["X-CSRFToken"] = token;
  }
  let res: Response;
  try {
    res = await fetch(`/api${path}${buildQuery(options.query)}`, { method, headers, body, credentials: "same-origin", signal: options.signal });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(0, "network_error", "Internet aloqasi yoki server mavjud emas.");
  }
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;
  const type = res.headers.get("Content-Type") || "";
  if (type.includes("application/json")) return (await res.json()) as T;
  return (await res.text()) as unknown as T;
}

export const get = <T,>(path: string, query?: Query) => api<T>(path, { query });
export const post = <T,>(path: string, body?: unknown) => api<T>(path, { method: "POST", body });
export const patch = <T,>(path: string, body?: unknown) => api<T>(path, { method: "PATCH", body });
export const put = <T,>(path: string, body?: unknown) => api<T>(path, { method: "PUT", body });
export const del = <T,>(path: string) => api<T>(path, { method: "DELETE" });

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Noma'lum xato.";
}
