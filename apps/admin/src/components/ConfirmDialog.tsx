import { createContext, useCallback, useContext, useRef, useState } from "react";

type ConfirmOptions = { message: string; confirmLabel?: string; danger?: boolean };
type ConfirmState = ConfirmOptions & { resolve: (v: boolean) => void };

const ConfirmCtx = createContext<(opts: ConfirmOptions | string) => Promise<boolean>>(
  () => Promise.resolve(false)
);

export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<ConfirmState | null>(null);
  const overlayRef = useRef<HTMLDivElement>(null);

  const confirm = useCallback((opts: ConfirmOptions | string) => {
    const options = typeof opts === "string" ? { message: opts } : opts;
    return new Promise<boolean>((resolve) => {
      setState({ ...options, resolve });
    });
  }, []);

  function respond(value: boolean) {
    state?.resolve(value);
    setState(null);
  }

  function handleOverlay(e: React.MouseEvent) {
    if (e.target === overlayRef.current) respond(false);
  }

  return (
    <ConfirmCtx.Provider value={confirm}>
      {children}
      {state && (
        <div
          ref={overlayRef}
          className="confirm-overlay"
          onClick={handleOverlay}
          role="dialog"
          aria-modal="true"
          aria-labelledby="confirm-msg"
        >
          <div className="confirm-dialog">
            <p id="confirm-msg" className="confirm-message">{state.message}</p>
            <div className="confirm-actions">
              <button
                className="btn-action cancel"
                onClick={() => respond(false)}
                autoFocus
              >
                Cancel
              </button>
              <button
                className={`btn-action ${state.danger !== false ? "delete" : "confirm"}`}
                onClick={() => respond(true)}
              >
                {state.confirmLabel ?? "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </ConfirmCtx.Provider>
  );
}

export function useConfirm() {
  return useContext(ConfirmCtx);
}
