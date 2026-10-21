import type { AuthResponse } from "@ama/shared-types";
import { NextResponse, type NextRequest } from "next/server";

import { clearAuthCookies, setAuthCookies } from "@/lib/auth-cookies";
import { API_URL, REFRESH_COOKIE } from "@/lib/backend";

function safeNext(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) {
    return "/";
  }
  return value;
}

export async function GET(request: NextRequest): Promise<NextResponse> {
  const nextPath = safeNext(request.nextUrl.searchParams.get("next"));
  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;

  if (refreshToken) {
    try {
      const response = await fetch(`${API_URL}/auth/refresh`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
        cache: "no-store",
      });
      if (response.ok) {
        const data = (await response.json()) as AuthResponse;
        const redirectResponse = NextResponse.redirect(new URL(nextPath, request.url));
        setAuthCookies(redirectResponse, data);
        return redirectResponse;
      }
    } catch {
      // Fall through to the sign-in redirect.
    }
  }

  const loginResponse = NextResponse.redirect(new URL("/login?expired=1", request.url));
  clearAuthCookies(loginResponse);
  return loginResponse;
}
