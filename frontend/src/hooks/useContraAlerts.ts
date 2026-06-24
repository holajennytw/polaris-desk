"use client";
import { useState, useEffect } from "react";
import { contraAlertStore, type ContraAlert, type ContraPage } from "@/lib/contraAlertStore";

export function useContraAlerts(page: ContraPage) {
  const [alerts, setAlerts] = useState<ContraAlert[]>([]);
  useEffect(() => {
    setAlerts(contraAlertStore.get(page));
    return contraAlertStore.subscribe(setAlerts, page);
  }, [page]);
  return alerts;
}
