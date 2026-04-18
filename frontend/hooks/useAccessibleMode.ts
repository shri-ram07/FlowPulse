"use client";
import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "flowpulse.accessibleMode";

/**
 * Persisted Accessible Mode toggle.
 *
 * Default behaviour:
 *  - If the user has a stored preference, honour it.
 *  - Otherwise, auto-enable when the OS exposes either
 *    `prefers-contrast: more` or `prefers-reduced-motion: reduce`.
 *
 * Side-effect: sets `data-accessible="on"` on <html> so CSS hooks can
 * style everything inside from one selector without prop-drilling.
 */
export function useAccessibleMode(): {
  on: boolean;
  toggle: () => void;
  set: (v: boolean) => void;
} {
  const [on, setOn] = useState<boolean>(false);

  useEffect(() => {
    let initial = false;
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored === "1") initial = true;
      else if (stored === "0") initial = false;
      else {
        initial =
          window.matchMedia("(prefers-contrast: more)").matches ||
          window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      }
    } catch {
      /* localStorage can fail in private mode */
    }
    setOn(initial);
  }, []);

  useEffect(() => {
    try {
      document.documentElement.setAttribute("data-accessible", on ? "on" : "off");
      window.localStorage.setItem(STORAGE_KEY, on ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [on]);

  const toggle = useCallback(() => setOn((v) => !v), []);
  const set = useCallback((v: boolean) => setOn(v), []);
  return { on, toggle, set };
}

/** `matchMedia('(prefers-reduced-motion: reduce)').matches` with SSR safety. */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(mq.matches);
    update();
    mq.addEventListener?.("change", update);
    return () => mq.removeEventListener?.("change", update);
  }, []);
  return reduced;
}
