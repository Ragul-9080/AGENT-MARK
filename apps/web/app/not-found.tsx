import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto flex min-h-screen max-w-lg flex-col items-center justify-center px-6 text-center">
      <p className="text-sm font-semibold uppercase tracking-widest text-indigo-600">404</p>
      <h1 className="mt-2 text-2xl font-semibold text-slate-900">We could not find that page</h1>
      <p className="mt-2 text-sm text-slate-500">
        The record may have been deleted, or the link may belong to another workspace.
      </p>
      <Link
        href="/"
        className="mt-6 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
      >
        Back to overview
      </Link>
    </div>
  );
}
