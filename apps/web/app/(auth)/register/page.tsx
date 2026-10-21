import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { AuthForm } from "@/components/auth-form";
import { ACCESS_COOKIE } from "@/lib/backend";

export const metadata = { title: "Create a workspace" };

export default async function RegisterPage() {
  const cookieStore = await cookies();
  if (cookieStore.get(ACCESS_COOKIE)) {
    redirect("/");
  }
  return <AuthForm mode="register" />;
}
