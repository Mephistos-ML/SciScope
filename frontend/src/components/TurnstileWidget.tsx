import { useEffect, useRef, useState } from "react";

const TURNSTILE_SCRIPT_ID = "sciscope-turnstile-script";
const TURNSTILE_SCRIPT_SRC =
  "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

type TurnstileWidgetProps = {
  onTokenChange: (token: string | null) => void;
  resetKey: number;
  siteKey: string | null;
};

type TurnstileInstance = {
  remove: (widgetId: string) => void;
  render: (
    container: HTMLElement,
    options: {
      callback: (token: string) => void;
      "error-callback": () => void;
      "expired-callback": () => void;
      sitekey: string;
      theme: "light";
    },
  ) => string;
};

declare global {
  interface Window {
    turnstile?: TurnstileInstance;
  }
}

let turnstileScriptPromise: Promise<void> | null = null;

export function TurnstileWidget({
  onTokenChange,
  resetKey,
  siteKey,
}: TurnstileWidgetProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const widgetIdRef = useRef<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    onTokenChange(null);
  }, [onTokenChange, resetKey]);

  useEffect(() => {
    if (!siteKey) {
      setLoadError(
        "Verification is required, but the Turnstile site key is not configured on this frontend.",
      );
      return;
    }

    let disposed = false;
    setLoadError(null);

    void loadTurnstileScript()
      .then(() => {
        if (disposed || !containerRef.current || !window.turnstile) {
          return;
        }

        containerRef.current.innerHTML = "";
        widgetIdRef.current = window.turnstile.render(containerRef.current, {
          sitekey: siteKey,
          theme: "light",
          callback: (token) => {
            onTokenChange(token);
            setLoadError(null);
          },
          "expired-callback": () => {
            onTokenChange(null);
          },
          "error-callback": () => {
            onTokenChange(null);
            setLoadError("Verification could not be completed. Reload the challenge and try again.");
          },
        });
      })
      .catch(() => {
        if (!disposed) {
          setLoadError("Verification could not be loaded right now. Please try again.");
        }
      });

    return () => {
      disposed = true;
      onTokenChange(null);
      if (widgetIdRef.current && window.turnstile) {
        window.turnstile.remove(widgetIdRef.current);
      }
      widgetIdRef.current = null;
      if (containerRef.current) {
        containerRef.current.innerHTML = "";
      }
    };
  }, [onTokenChange, resetKey, siteKey]);

  return (
    <div className="turnstile-widget-block">
      <div className="turnstile-widget-container" ref={containerRef} />
      {loadError ? <p className="turnstile-widget-error">{loadError}</p> : null}
    </div>
  );
}

function loadTurnstileScript(): Promise<void> {
  if (window.turnstile) {
    return Promise.resolve();
  }

  if (turnstileScriptPromise) {
    return turnstileScriptPromise;
  }

  turnstileScriptPromise = new Promise<void>((resolve, reject) => {
    const existingScript = document.getElementById(TURNSTILE_SCRIPT_ID) as HTMLScriptElement | null;
    if (existingScript) {
      existingScript.addEventListener("load", () => resolve(), { once: true });
      existingScript.addEventListener("error", () => reject(new Error("Failed to load Turnstile.")), {
        once: true,
      });
      return;
    }

    const script = document.createElement("script");
    script.id = TURNSTILE_SCRIPT_ID;
    script.src = TURNSTILE_SCRIPT_SRC;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Failed to load Turnstile."));
    document.head.appendChild(script);
  });

  return turnstileScriptPromise;
}
