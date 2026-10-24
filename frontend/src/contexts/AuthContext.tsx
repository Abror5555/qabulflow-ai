import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useMemo, type ReactNode } from "react";
import { ApiError, get, post } from "../lib/api";
import { ROLE_LEVEL } from "../lib/constants";
import { setOrgTimeZone } from "../lib/format";
import type { Me, Role } from "../lib/types";

interface AuthValue {
  me: Me | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<Me>;
  logout: () => Promise<void>;
  switchOrg: (id: number) => Promise<void>;
  can: (role: Role) => boolean;
  refresh: () => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      try {
        const me = await get<Me & { authenticated?: boolean }>("/auth/me/");
        if (me.authenticated === false) return null;
        setOrgTimeZone(me.organization?.timezone);
        return me;
      } catch (e) {
        if (e instanceof ApiError && (e.status === 401 || e.status === 403)) return null;
        throw e;
      }
    },
    staleTime: 60_000,
    retry: false,
  });

  const login = useCallback(
    async (email: string, password: string) => {
      const me = await post<Me>("/auth/login/", { email, password });
      setOrgTimeZone(me.organization?.timezone);
      qc.removeQueries({ predicate: (q) => q.queryKey[0] !== "me" });
      qc.setQueryData(["me"], me);
      return me;
    },
    [qc],
  );

  const logout = useCallback(async () => {
    try {
      await post("/auth/logout/");
    } finally {
      qc.removeQueries({ predicate: (q) => q.queryKey[0] !== "me" });
      qc.setQueryData(["me"], null);
    }
  }, [qc]);

  const switchOrg = useCallback(
    async (id: number) => {
      const me = await post<Me>("/auth/switch-organization/", { organization_id: id });
      setOrgTimeZone(me.organization?.timezone);
      qc.removeQueries({ predicate: (q) => q.queryKey[0] !== "me" });
      qc.setQueryData(["me"], me);
    },
    [qc],
  );

  const value = useMemo<AuthValue>(
    () => ({
      me: query.data ?? null,
      loading: query.isLoading,
      login,
      logout,
      switchOrg,
      can: (role: Role) => !!query.data?.role && ROLE_LEVEL[query.data.role] >= ROLE_LEVEL[role],
      refresh: () => void query.refetch(),
    }),
    [query, login, logout, switchOrg],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth AuthProvider ichida ishlatilishi kerak");
  return ctx;
}
