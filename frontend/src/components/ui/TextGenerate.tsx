"use client";
import { motion } from "framer-motion";

interface TextGenerateProps {
  text: string;
  className?: string;
  delay?: number;
}

export function TextGenerate({ text, className, delay = 0 }: TextGenerateProps) {
  const words = text.split(" ");
  return (
    <span className={className}>
      {words.map((word, i) => (
        <motion.span
          key={i}
          initial={{ opacity: 0, x: 12 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{
            delay: delay + Math.min(i * 0.035, 0.8),
            duration: 0.28,
            ease: "easeOut",
          }}
          style={{ display: "inline-block", marginRight: "0.28em" }}
        >
          {word}
        </motion.span>
      ))}
    </span>
  );
}
