"use client";

import { useSearchParams } from "next/navigation";

/**
 * Returns the active well ID from the URL ?well= query param.
 * Defaults to "BGW-01" so all existing single-well behaviour is preserved
 * when the param is absent.
 */
export function useWellId(): string {
  const params = useSearchParams();
  return params.get("well") ?? "BGW-01";
}
