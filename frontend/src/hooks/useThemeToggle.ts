"use client";
import { useEffect, useRef, useState } from "react";
import { useTheme } from "next-themes";

export function useThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const isDark = mounted && resolvedTheme === "dark";
  const btnRef = useRef<HTMLButtonElement>(null);

  const toggleTheme = () => {
    const next = isDark ? "light" : "dark";
    const rect = btnRef.current?.getBoundingClientRect();
    const cx = rect ? rect.left + rect.width / 2 : window.innerWidth - 26;
    const cy = rect ? rect.top + rect.height / 2 : 26;

    // 星星粒子（先於 View Transition 爆散）
    if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      const N = 8;
      const colors = ["", "", "", "rgba(255,255,255,0.82)", "", "", "", "rgba(255,255,255,0.70)"];
      for (let i = 0; i < N; i++) {
        const angle = (i / N) * Math.PI * 2 - Math.PI / 2;
        const dist = 18 + Math.random() * 26;
        const el = document.createElement("span");
        el.className = "theme-sparkle";
        el.style.left = `${cx}px`;
        el.style.top = `${cy}px`;
        el.style.setProperty("--tx", `${Math.cos(angle) * dist}px`);
        el.style.setProperty("--ty", `${Math.sin(angle) * dist}px`);
        el.style.setProperty("--sz", `${0.55 + Math.random() * 0.8}`);
        el.style.setProperty("--dur", `${0.46 + Math.random() * 0.28}s`);
        el.style.setProperty("--delay", `${i * 15}ms`);
        if (colors[i]) el.style.setProperty("--color", colors[i]);
        document.body.appendChild(el);
        el.addEventListener("animationend", () => el.remove(), { once: true });
      }
    }

    // View Transition 放射展開
    const root = document.documentElement;
    root.style.setProperty("--vt-x", `${cx}px`);
    root.style.setProperty("--vt-y", `${cy}px`);
    if ("startViewTransition" in document) {
      (document as Document & { startViewTransition: (cb: () => void) => void })
        .startViewTransition(() => setTheme(next));
    } else {
      setTheme(next);
    }
  };

  return { isDark, toggleTheme, btnRef };
}
