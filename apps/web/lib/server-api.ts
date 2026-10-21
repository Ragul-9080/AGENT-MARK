import "server-only";

import type { ApiErrorBody } from "@ama/shared-types";
import { cookies } from "next/headers";
import { notFound, redirect } from "next/navigation";

import { ACCESS_COOKIE, API_URL } from "@/lib/backend";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function refreshRedirect(nextPath: string): never {
  redirect(`/api/auth/refresh-session?next=${encodeURIComponent(nextPath)}`);
}

export async function serverApi<T>(path: string, nextPath: string): Promise<T> {
  const cookieStore = await cookies();
  const token = cookieStore.get(ACCESS_COOKIE)?.value;

  if (!token) {
    refreshRedirect(nextPath);
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      headers: { Authorization: `Bearer ${token}`, accept: "application/json" },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(503, "The API is not reachable. Check that it is running.");
  }

  if (response.status === 401) {
    refreshRedirect(nextPath);
  }
  if (response.status === 404) {
    notFound();
  }
  if (!response.ok) {
    let message = `The API returned ${response.status}.`;
    try {
      const body = (await response.json()) as ApiErrorBody;
      message = body.error?.message ?? message;
    } catch {
      // Keep the status-based fallback.
    }
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
