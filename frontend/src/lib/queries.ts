import { useQuery } from "@tanstack/react-query";
import { get } from "./api";
import type { Branch, Course, Group, Paginated } from "./types";

export function useBranches() {
  return useQuery({
    queryKey: ["branches"],
    queryFn: () => get<Paginated<Branch>>("/branches/", { page_size: 200 }).then((r) => r.results),
    staleTime: 5 * 60_000,
  });
}

export function useCourses(activeOnly = false) {
  return useQuery({
    queryKey: ["courses", "all"],
    queryFn: () => get<Paginated<Course>>("/courses/", { page_size: 200 }).then((r) => r.results),
    staleTime: 60_000,
    select: (list) => (activeOnly ? list.filter((c) => c.is_active) : list),
  });
}

export function useGroups() {
  return useQuery({
    queryKey: ["groups", "all"],
    queryFn: () => get<Paginated<Group>>("/groups/", { page_size: 200 }).then((r) => r.results),
    staleTime: 60_000,
  });
}

export function useAssignable() {
  return useQuery({
    queryKey: ["team", "assignable"],
    queryFn: () => get<{ user_id: number; full_name: string; role: string; initials: string }[]>("/team/assignable/"),
    staleTime: 5 * 60_000,
  });
}
