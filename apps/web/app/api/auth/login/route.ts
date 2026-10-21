import type { AuthResponse } from "@ama/shared-types";
import { NextResponse, type NextRequest } from "next/server";

import { setAuthCookies } from "@/lib/auth-cookies";
import { API_URL } from "@/lib/backend";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const payload = (await request.json().catch(() => null)) as Record<string, unknown> | null;
  if (!payload) {
    return NextResponse.json(
      { error: { message: "Enter your email and password.", code: "invalid_request" } },
      { status: 400 },
    );
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL}/auth/login`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      { error: { message: "The API is not reachable. Try again shortly.", code: "api_unreachable" } },
      { status: 503 },
    );
  }

  const data = (await response.json()) as AuthResponse & {
    error?: { message?: string; code?: string };
  };
  if (!response.ok) {
    return NextResponse.json(
      {
        error: {
          message: data.error?.message ?? "Sign in failed.",
          code: data.error?.code ?? "login_failed",
        },
      },
      { status: response.status },
    );
  }

  const result = NextResponse.json({ user: data.user, workspace: data.workspace });
  setAuthCookies(result, data);
  return result;
}
