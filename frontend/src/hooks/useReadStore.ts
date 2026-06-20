"use client";
import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "polaris-read";

function getRead(): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return new Set(raw ? JSON.parse(raw) : []);
  } catch {
    return new Set();
  }
}

function saveRead(set: Set<string>) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...set]));
}

// 全域單例 store（跨 hook 實例共享）
let _read = getRead();
const _listeners = new Set<() => void>();

function notify() { _listeners.forEach((fn) => fn()); }

export const ReadStore = {
  isRead: (id: string) => _read.has(id),
  markRead: (id: string) => {
    if (!_read.has(id)) {
      _read = new Set([..._read, id]);
      saveRead(_read);
      notify();
    }
  },
  getCount: () => _read.size,
};

export function useReadStore() {
  const [, forceRender] = useState(0);
  useEffect(() => {
    const fn = () => forceRender((n) => n + 1);
    _listeners.add(fn);
    return () => { _listeners.delete(fn); };
  }, []);
  return ReadStore;
}
