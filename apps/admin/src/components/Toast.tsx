import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";

type ToastKind = "success" | "error" | "info";
type Toast = { id: number; kind: ToastKind; message: string };

type ToastApi = {
  /** Show a toast. Defaults to success. Auto-dismisses after `ms` (default 2500). */
  show: (message: string, kind?: ToastKind, ms?: number) => void;
  success: (message: string, ms?: number) => void;
  error: (message: string, ms?: number) => void;
};

const ToastContext = createContext<ToastApi | null>(null);

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within <ToastProvider>");
  return ctx;
}

const ICONS: Record<ToastKind, string> = { success: "✓", error: "✕", info: "ℹ" };

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const remove = useCallback((id: number) => {
    setToasts((ts) => ts.filter((t) => t.id !== id));
  }, []);

  const show = useCallback(
    (message: string, kind: ToastKind = "success", ms = 2500) => {
      const id = nextId.current++;
      setToasts((ts) => [...ts, { id, kind, message }]);
      window.setTimeout(() => remove(id), ms);
    },
    [remove]
  );

  const success = useCallback((message: string, ms?: number) => show(message, "success", ms), [show]);
  const error = useCallback((message: string, ms?: number) => show(message, "error", ms), [show]);

  return (
    <ToastContext.Provider value={{ show, success, error }}>
      {children}
      <div className="toast-container" role="status" aria-live="polite" data-testid="toast-container">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.kind}`} data-testid="toast" onClick={() => remove(t.id)}>
            <span className="toast-icon" aria-hidden>{ICONS[t.kind]}</span>
            <span className="toast-msg">{t.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
