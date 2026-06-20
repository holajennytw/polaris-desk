"use client";
import useSWR from "swr";
import { api } from "@/lib/api";
import type { CompanyVM } from "@/types/viewmodel";

export function useCompanies(): CompanyVM[] {
  const { data } = useSWR("companies", () => api.companies(), {
    revalidateOnFocus: false,
  });
  return data ?? [];
}
