"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";

export type ToastKind = "success" | "error" | "info";

interface ToastItem { id: string; kind: ToastKind; text: string; }

interface ToastCtx { push: (kind: ToastKind, text: string) => void; }

const Ctx = createContext<ToastCtx>({ push: () => {} });

export function useToast() {
  return useContext(Ctx);
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const push = useCallback((kind: ToastKind, text: string) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((t) => [...t, { id, kind, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3500);
  }, []);

  return (
    <Ctx.Provider value={{ push }}>
      {children}
      <div className="toast-stack" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.kind}`}>
            <span aria-hidden>
              {t.kind === "success" ? "✅" : t.kind === "error" ? "⚠" : "ℹ"}
            </span>
            <span>{t.text}</span>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
