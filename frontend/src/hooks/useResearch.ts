"use client";
import useSWRMutation from "swr/mutation";
import { api } from "@/lib/api";

async function researchFetcher(_key: string, { arg }: { arg: string }) {
  return api.research(arg);
}

export function useResearch() {
  return useSWRMutation("research", researchFetcher);
}
