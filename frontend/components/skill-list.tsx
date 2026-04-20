"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useCallback, Suspense } from "react";
import Link from "next/link";
import { SkillCard } from "./skill-card";
import { SortSelect } from "./sort-select";
import type { PaginatedSkills, SortOption } from "@/types/skill";
import { ChevronLeft, ChevronRight } from "lucide-react";

interface SkillListProps {
  data: PaginatedSkills;
  sort: SortOption;
  q: string;
  labels: string[];
}

export function SkillList({ data, sort, q, labels }: SkillListProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const pathname = usePathname();

  const setPage = useCallback(
    (page: number) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("page", String(page));
      router.push(`${pathname}?${params}`);
    },
    [router, searchParams, pathname],
  );

  const removeLabel = useCallback(
    (label: string) => {
      const params = new URLSearchParams(searchParams.toString());
      const current = params.get("labels")?.split(",").filter(Boolean) ?? [];
      const next = current.filter((l) => l !== label);
      if (next.length) params.set("labels", next.join(","));
      else params.delete("labels");
      params.delete("page");
      router.push(`${pathname}?${params}`);
    },
    [router, searchParams, pathname],
  );

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-sm text-muted-foreground">
          {data.total} skill{data.total !== 1 ? "s" : ""}
          {q && <> matching &ldquo;{q}&rdquo;</>}
        </span>
        <div className="ml-auto flex items-center gap-2">
          {labels.map((l) => (
            <button
              key={l}
              onClick={() => removeLabel(l)}
              className="inline-flex items-center gap-1 rounded-full bg-secondary text-secondary-foreground px-2 py-0.5 text-xs hover:bg-secondary/80 transition-colors"
            >
              {l} ×
            </button>
          ))}
          <Suspense fallback={null}>
            <SortSelect current={sort} />
          </Suspense>
        </div>
      </div>

      {/* Cards */}
      {data.items.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <p>No skills found.</p>
          {q && (
            <Link href="/skills" className="text-primary underline text-sm mt-1 inline-block">
              Clear search
            </Link>
          )}
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {data.items.map((skill) => (
            <SkillCard key={skill.id} skill={skill} />
          ))}
        </div>
      )}

      {/* Pagination */}
      {data.pages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-4">
          <button
            onClick={() => setPage(data.page - 1)}
            disabled={data.page <= 1}
            className="inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-sm disabled:opacity-40 hover:bg-muted transition-colors"
          >
            <ChevronLeft className="h-4 w-4" />
            Prev
          </button>
          <span className="text-sm text-muted-foreground">
            {data.page} / {data.pages}
          </span>
          <button
            onClick={() => setPage(data.page + 1)}
            disabled={data.page >= data.pages}
            className="inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-sm disabled:opacity-40 hover:bg-muted transition-colors"
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}
