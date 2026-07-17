import type {
  SignalDetailPayload,
  SignalListPayload,
  StatusPayload,
} from "../types/api";

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

export async function fetchStatus(): Promise<StatusPayload> {
  const response = await fetch("/api/status");
  return readJson<StatusPayload>(response);
}

export async function fetchSignals(): Promise<SignalListPayload> {
  const response = await fetch("/api/signals");
  return readJson<SignalListPayload>(response);
}

export async function fetchSignalDetail(itemId: string): Promise<SignalDetailPayload> {
  const response = await fetch(`/api/signals/${itemId}`);
  return readJson<SignalDetailPayload>(response);
}

export async function startScan(): Promise<StatusPayload> {
  const response = await fetch("/api/start", {
    method: "POST",
  });
  return readJson<StatusPayload>(response);
}

export async function stopScan(): Promise<StatusPayload> {
  const response = await fetch("/api/stop", {
    method: "POST",
  });
  return readJson<StatusPayload>(response);
}
