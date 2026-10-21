import type { ApiErrorBody } from "@ama/shared-types";

export class ClientApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ClientApiError";
  }
}

async function parseError(response: Response): Promise<ClientApiError> {
  let message = `Request failed (${response.status}).`;
  try {
    const body = (await response.json()) as ApiErrorBody;
    message = body.error?.message ?? message;
  } catch {
    // Keep the status-based fallback.
  }
  return new ClientApiError(response.status, message);
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("content-type", "application/json");
  }

  const response = await fetch(`/api/backend${path}`, {
    ...init,
    headers,
    credentials: "same-origin",
  });

  if (response.status === 401) {
    // This module is not a React component, so a full navigation is the only option.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign(`/login?expired=1`);
    throw new ClientApiError(401, "Your session expired. Please sign in again.");
  }
  if (!response.ok) {
    throw await parseError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
