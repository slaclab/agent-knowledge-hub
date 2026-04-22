"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useCallback, useState, useRef, useEffect } from "react";
import { ChevronDown } from "lucide-react";
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
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const currentLabel = SORT_OPTIONS.find((o) => o.value === current)?.label ?? "Sort";

  const onChange = useCallback(
    (value: SortOption) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("sort", value);
      params.delete("page");
      router.push(`${pathname}?${params}`);
      setOpen(false);
    },
    [router, searchParams, pathname],
  );

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs bg-background hover:bg-muted transition-colors"
      >
        {currentLabel}
        <ChevronDown className="h-3 w-3 opacity-60" />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 z-20 w-36 rounded-md border bg-white dark:bg-zinc-900 shadow-lg">
          <div className="p-1">
            {SORT_OPTIONS.map((o) => (
              <button
                key={o.value}
                onClick={() => onChange(o.value)}
                className={`flex w-full items-center rounded px-2 py-1 text-xs transition-colors ${
                  o.value === current ? "font-medium bg-muted" : "hover:bg-muted"
                }`}
              >
                {o.label}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
