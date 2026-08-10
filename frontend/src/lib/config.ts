export type AuthMode = "disabled" | "dev";

type FrontendConfig = {
  apiBaseUrl: string;
  authMode: AuthMode;
  requestTimeoutMs: number;
};

const DEFAULT_REQUEST_TIMEOUT_MS = 15_000;

function readRequiredEnv(name: string, value: unknown): string {
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`Missing required frontend environment variable: ${name}`);
  }

  return value.trim();
}

function readAuthMode(): AuthMode {
  const value = readRequiredEnv("VITE_AUTH_MODE", import.meta.env.VITE_AUTH_MODE);

  if (value === "disabled" || value === "dev") {
    return value;
  }

  throw new Error(
    `Unsupported VITE_AUTH_MODE value "${value}". Expected "disabled" or "dev".`,
  );
}

function readApiBaseUrl(): string {
  return readRequiredEnv("VITE_API_BASE_URL", import.meta.env.VITE_API_BASE_URL).replace(
    /\/+$/,
    "",
  );
}

export const frontendConfig: FrontendConfig = Object.freeze({
  apiBaseUrl: readApiBaseUrl(),
  authMode: readAuthMode(),
  requestTimeoutMs: DEFAULT_REQUEST_TIMEOUT_MS,
});
