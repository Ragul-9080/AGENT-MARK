import type { AuthResponse } from "@ama/shared-types";
import { NextResponse, type NextRequest } from "next/server";

import { clearAuthCookies, setAuthCookies } from "@/lib/auth-cookies";
import { ACCESS_COOKIE, API_URL, REFRESH_COOKIE } from "@/lib/backend";

type RouteContext = { params: Promise<{ path: string[] }> };

async function refreshSession(request: NextRequest): Promise<AuthResponse | null> {
  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;
  if (!refreshToken) return null;

  try {
    const response = await fetch(`${API_URL}/auth/refresh`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: "no-store",
    });
    if (!response.ok) return null;
    return (await response.json()) as AuthResponse;
  } catch {
    return null;
  }
}

async function forward(
  request: NextRequest,
  target: string,
  token: string,
): Promise<Response> {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    accept: request.headers.get("accept") ?? "application/json",
    "cache-control": "no-store",
  };
  const contentType = request.headers.get("content-type");
  if (contentType) headers["content-type"] = contentType;

  const method = request.method.toUpperCase();
  const hasBody = !["GET", "HEAD"].includes(method);
  const body = hasBody ? await request.arrayBuffer() : undefined;

  return fetch(target, {
    method,
    headers,
    body: body && body.byteLength > 0 ? body : undefined,
    cache: "no-store",
    redirect: "manual",
  });
}

async function proxy(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  const { path } = await context.params;
  const target = `${API_URL}/${path.join("/")}${request.nextUrl.search}`;

  let token = request.cookies.get(ACCESS_COOKIE)?.value;
  let refreshed: AuthResponse | null = null;

  if (!token) {
    refreshed = await refreshSession(request);
    token = refreshed?.access_token;
  }
  if (!token) {
    const unauthorized = NextResponse.json(
      { error: { code: "unauthorized", message: "Please sign in to continue." } },
      { status: 401 },
    );
    clearAuthCookies(unauthorized);
    return unauthorized;
  }

  let upstream: Response;
  try {
    upstream = await forward(request, target, token);
  } catch {
    return NextResponse.json(
      { error: { code: "api_unreachable", message: "The API is not reachable." } },
      { status: 503 },
    );
  }

  if (upstream.status === 401) {
    refreshed = await refreshSession(request);
    if (refreshed) {
      try {
        upstream = await forward(request, target, refreshed.access_token);
      } catch {
        return NextResponse.json(
          { error: { code: "api_unreachable", message: "The API is not reachable." } },
          { status: 503 },
        );
      }
    }
  }

  const response = new NextResponse(upstream.status === 204 ? null : upstream.body, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "application/json",
      "cache-control": "no-store",
    },
  });

  if (refreshed) {
    setAuthCookies(response, refreshed);
  }
  if (upstream.status === 401) {
    clearAuthCookies(response);
  }
  return response;
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const PUT = proxy;
export const DELETE = proxy;
