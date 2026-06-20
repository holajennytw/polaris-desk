"use client";
import useSWRMutation from "swr/mutation";
import { api } from "@/lib/api";

async function askFetcher(_key: string, { arg }: { arg: string }) {
  return api.ask(arg);
}

export function useAsk() {
  return useSWRMutation("ask", askFetcher);
}
