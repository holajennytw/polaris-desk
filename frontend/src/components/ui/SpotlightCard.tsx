"use client";
import { useState } from "react";
import { useMotionTemplate, useMotionValue, motion } from "framer-motion";
import { cn } from "@/lib/utils";
import type { ComponentPropsWithoutRef } from "react";

function useSpotlight() {
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  const [hovered, setHovered] = useState(false);

  const background = useMotionTemplate`radial-gradient(320px circle at ${mouseX}px ${mouseY}px, rgb(var(--primary) / .13), transparent 80%)`;

  const handlers = {
    onMouseMove({ currentTarget, clientX, clientY }: React.MouseEvent<HTMLElement>) {
      const { left, top } = currentTarget.getBoundingClientRect();
      mouseX.set(clientX - left);
      mouseY.set(clientY - top);
    },
    onMouseEnter: () => setHovered(true),
    onMouseLeave: () => setHovered(false),
  };

  return { background, hovered, handlers };
}

interface SpotlightCardProps extends ComponentPropsWithoutRef<"div"> {}

export function SpotlightCard({ children, className, ...props }: SpotlightCardProps) {
  const { background, hovered, handlers } = useSpotlight();

  return (
    <div className={cn("relative", className)} {...handlers} {...props}>
      <motion.div
        animate={{ opacity: hovered ? 1 : 0 }}
        transition={{ duration: 0.25 }}
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: "inherit",
          background,
          pointerEvents: "none",
          zIndex: 0,
        }}
      />
      <div style={{ position: "relative", zIndex: 1 }}>{children}</div>
    </div>
  );
}

interface SpotlightButtonProps extends ComponentPropsWithoutRef<"button"> {}

export function SpotlightButton({ children, className, ...props }: SpotlightButtonProps) {
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  const [hovered, setHovered] = useState(false);

  const background = useMotionTemplate`radial-gradient(280px circle at ${mouseX}px ${mouseY}px, rgb(var(--primary) / .13), transparent 80%)`;

  return (
    <button
      className={cn("relative", className)}
      onMouseMove={({ currentTarget, clientX, clientY }) => {
        const { left, top } = currentTarget.getBoundingClientRect();
        mouseX.set(clientX - left);
        mouseY.set(clientY - top);
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      {...props}
    >
      <motion.div
        animate={{ opacity: hovered ? 1 : 0 }}
        transition={{ duration: 0.25 }}
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: "inherit",
          background,
          pointerEvents: "none",
          zIndex: 0,
        }}
      />
      <div style={{ position: "relative", zIndex: 1, display: "contents" }}>{children}</div>
    </button>
  );
}
