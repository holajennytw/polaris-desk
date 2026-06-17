"use client";
import { useState, useEffect } from "react";
import { contraAlertStore, type ContraAlert } from "@/lib/contraAlertStore";

export function useContraAlerts() {
  const [alerts, setAlerts] = useState<ContraAlert[]>([]);
  useEffect(() => {
    setAlerts(contraAlertStore.get());
    return contraAlertStore.subscribe(setAlerts);
  }, []);
  return alerts;
}
