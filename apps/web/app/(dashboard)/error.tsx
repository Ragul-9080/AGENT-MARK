"use client";

import { useEffect } from "react";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="rounded-xl border border-rose-200 bg-rose-50 p-8">
      <h1 className="text-lg font-semibold text-rose-900">This page could not load</h1>
      <p className="mt-2 max-w-xl text-sm text-rose-700">
        {error.message || "An unexpected error occurred while talking to the API."}
      </p>
      <button
        type="button"
        onClick={reset}
        className="mt-4 rounded-lg bg-rose-900 px-3.5 py-2 text-sm font-medium text-white hover:bg-rose-700"
      >
        Try again
      </button>
    </div>
  );
}
