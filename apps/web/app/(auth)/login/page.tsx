import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { AuthForm } from "@/components/auth-form";
import { ACCESS_COOKIE } from "@/lib/backend";

export const metadata = { title: "Sign in" };

type SearchParams = Promise<{ expired?: string }>;

export default async function LoginPage({ searchParams }: { searchParams: SearchParams }) {
  const [params, cookieStore] = await Promise.all([searchParams, cookies()]);
  if (cookieStore.get(ACCESS_COOKIE)) {
    redirect("/");
  }

  return (
    <AuthForm
      mode="login"
      notice={
        params.expired
          ? "Your session expired. Sign in again to continue where you left off."
          : undefined
      }
    />
  );
}
