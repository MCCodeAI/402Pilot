import type { ReactNode } from "react";
import styles from "./Caption.module.css";

interface CaptionProps {
  /** Optional title (small caps eyebrow). */
  label?: string;
  children: ReactNode;
}

/**
 * Inline chart caption (≤ 60 words). The convention from
 * `docs/code_structure.md` is that every chart has one. Captions are
 * content, not decoration: they explain *what the reader is looking at*
 * and *why it matters*.
 */
export default function Caption({ label, children }: CaptionProps) {
  return (
    <figcaption className={styles.caption}>
      {label && <span className={styles.label}>{label}</span>}
      <span className={styles.body}>{children}</span>
    </figcaption>
  );
}
