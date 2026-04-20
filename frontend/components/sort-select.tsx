"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useCallback } from "react";
import type { SortOption } from "@/types/skill";

const SORT_OPTIONS: { value: SortOption; label: string }[] = [
  { value: "newest", label: "Newest" },
  { value: "highest_rated", label: "Highest Rated" },
  { value: "most_rated", label: "Most Rated" },
  { value: "most_stars", label: "Most Stars" },
];

export function SortSelect({ current }: { current: SortOption }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const pathname = usePathname();

  const onChange = useCallback(
    (value: SortOption) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("sort", value);
      params.delete("page");
      router.push(`${pathname}?${params}`);
    },
    [router, searchParams, pathname],
  );

  return (
    <select
      value={current}
      onChange={(e) => onChange(e.target.value as SortOption)}
      className="rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
    >
      {SORT_OPTIONS.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}
