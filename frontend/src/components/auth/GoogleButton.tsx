import { useEffect, useRef, useState } from "react";

import { useAuth } from "../../context/AuthContext";

const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;
const GSI_SRC = "https://accounts.google.com/gsi/client";

interface GoogleAccounts {
  accounts: {
    id: {
      initialize: (config: { client_id: string; callback: (r: { credential: string }) => void }) => void;
      renderButton: (el: HTMLElement, opts: Record<string, unknown>) => void;
    };
  };
}
declare global {
  interface Window {
    google?: GoogleAccounts;
  }
}

function loadGsi(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) return resolve();
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${GSI_SRC}"]`);
    if (existing) {
      existing.addEventListener("load", () => resolve());
      existing.addEventListener("error", () => reject(new Error("gsi load failed")));
      return;
    }
    const script = document.createElement("script");
    script.src = GSI_SRC;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("gsi load failed"));
    document.head.appendChild(script);
  });
}

/** "Continue with Google" via Google Identity Services. Falls back to a disabled
 * placeholder when no client ID is configured, so the UI never half-renders. */
export function GoogleButton({ onError }: { onError?: (message: string) => void }) {
  const { loginWithGoogle } = useAuth();
  const holder = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!CLIENT_ID || !holder.current) return;
    let cancelled = false;
    loadGsi()
      .then(() => {
        if (cancelled || !window.google || !holder.current) return;
        window.google.accounts.id.initialize({
          client_id: CLIENT_ID,
          callback: (response) => {
            loginWithGoogle(response.credential).catch((err: unknown) =>
              onError?.(err instanceof Error ? err.message : String(err)),
            );
          },
        });
        window.google.accounts.id.renderButton(holder.current, {
          theme: "outline",
          size: "large",
          width: 320,
          text: "continue_with",
          shape: "rectangular",
          logo_alignment: "left",
        });
      })
      .catch(() => setFailed(true));
    return () => {
      cancelled = true;
    };
  }, [loginWithGoogle, onError]);

  if (!CLIENT_ID) {
    return (
      <button type="button" className="btn btn--ghost google-btn google-btn--placeholder" disabled>
        <GoogleGlyph />
        Google (нужен VITE_GOOGLE_CLIENT_ID)
      </button>
    );
  }

  if (failed) {
    return (
      <button type="button" className="btn btn--ghost google-btn" disabled>
        <GoogleGlyph />
        Google недоступен
      </button>
    );
  }

  return <div className="google-btn__holder" ref={holder} />;
}

function GoogleGlyph() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62Z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18Z"
      />
      <path
        fill="#FBBC05"
        d="M3.97 10.72a5.4 5.4 0 0 1 0-3.44V4.95H.96a9 9 0 0 0 0 8.1l3.01-2.33Z"
      />
      <path
        fill="#EA4335"
        d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58C13.47.9 11.43 0 9 0A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58Z"
      />
    </svg>
  );
}
