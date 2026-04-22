"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { Tag, X, ChevronDown } from "lucide-react";
import type { LabelOut } from "@/types/skill";

export function LabelFilter({ activeLabels }: { activeLabels: string[] }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [suggestions, setSuggestions] = useState<LabelOut[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    const qs = new URLSearchParams();
    if (q) qs.set("q", q);
    qs.set("limit", "20");
    fetch(`/api/labels?${qs}`, { signal: controller.signal })
      .then((r) => r.json())
      .then((data: LabelOut[]) => setSuggestions(data))
      .catch(() => {});
    return () => controller.abort();
  }, [q]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const toggleLabel = useCallback(
    (name: string) => {
      const params = new URLSearchParams(searchParams.toString());
      const current = params.get("labels")?.split(",").filter(Boolean) ?? [];
      const next = current.includes(name)
        ? current.filter((l) => l !== name)
        : [...current, name];
      if (next.length) params.set("labels", next.join(","));
      else params.delete("labels");
      params.delete("page");
      router.push(`${pathname}?${params}`);
    },
    [router, searchParams, pathname],
  );

  const filtered = suggestions.filter((s) => !activeLabels.includes(s.name));

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs transition-colors ${
          activeLabels.length > 0
            ? "bg-primary text-primary-foreground border-primary"
            : "bg-background hover:bg-muted"
        }`}
      >
        <Tag className="h-3 w-3" />
        Labels
        {activeLabels.length > 0 && (
          <span className="rounded-full bg-primary-foreground/20 px-1 text-xs tabular-nums">
            {activeLabels.length}
          </span>
        )}
        <ChevronDown className="h-3 w-3 opacity-60" />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 z-20 w-56 rounded-md border bg-white dark:bg-zinc-900 shadow-lg">
          <div className="p-2 border-b">
            <input
              autoFocus
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search labels…"
              className="w-full rounded border border-input bg-background px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
          <div className="max-h-52 overflow-y-auto p-1">
            {activeLabels.map((name) => (
              <button
                key={name}
                onClick={() => toggleLabel(name)}
                className="flex w-full items-center justify-between rounded px-2 py-1 text-xs hover:bg-muted transition-colors"
              >
                <span className="font-medium">{name}</span>
                <X className="h-3 w-3 text-muted-foreground" />
              </button>
            ))}
            {filtered.length === 0 && activeLabels.length === 0 && (
              <p className="px-2 py-3 text-xs text-muted-foreground text-center">
                {q ? "No labels match." : "No labels yet."}
              </p>
            )}
            {filtered.map((label) => (
              <button
                key={label.name}
                onClick={() => toggleLabel(label.name)}
                className="flex w-full items-center justify-between rounded px-2 py-1 text-xs hover:bg-muted transition-colors"
              >
                <span>{label.name}</span>
                <span className="text-muted-foreground tabular-nums">{label.usage_count}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
