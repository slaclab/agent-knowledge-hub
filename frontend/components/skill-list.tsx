"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useCallback, Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { SkillCard } from "./skill-card";
import { SortSelect } from "./sort-select";
import { LabelFilter } from "./label-filter";
import { PlatformFilter } from "./platform-filter";
import type { PaginatedSkills, SortOption, VisibilityType } from "@/types/skill";
import { ChevronLeft, ChevronRight } from "lucide-react";

const CURSOR_THRESHOLD = 10; // pages beyond this use cursor instead of skip

interface SkillListProps {
  data: PaginatedSkills;
  sort: SortOption;
  q: string;
  labels: string[];
  platforms: string[];
  forkedFrom?: string;
  visibility?: VisibilityType | "all";
  accessInstructionsUrl?: string;
}

const VISIBILITY_OPTIONS: { value: VisibilityType | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "public", label: "Public Only" },
  { value: "internal", label: "SLAC Only" },
];

export function SkillList({ data, sort, q, labels, platforms, forkedFrom, visibility, accessInstructionsUrl }: SkillListProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const pathname = usePathname();

  // Track cursors in component state so they don't appear in the URL
  const [nextCursor, setNextCursor] = useState<string | null>(data.next_cursor ?? null);
  const pageInputRef = useRef<HTMLInputElement>(null);
  const [pageInputError, setPageInputError] = useState(false);

  // Keep cursor state in sync when data changes (e.g. after navigation)
  useEffect(() => {
    setNextCursor(data.next_cursor ?? null);
  }, [data.next_cursor]);

  // Redirect stale bookmarks (empty result with page > 1)
  useEffect(() => {
    if (data.items.length === 0 && data.page > 1) {
      const params = new URLSearchParams(searchParams.toString());
      params.set("page", "1");
      router.replace(`${pathname}?${params}`);
    }
  }, [data.items.length, data.page, router, searchParams, pathname]);

  useEffect(() => {
    router.refresh();

    function onPageShow(e: PageTransitionEvent) {
      if (e.persisted) router.refresh();
    }
    window.addEventListener("pageshow", onPageShow);
    return () => window.removeEventListener("pageshow", onPageShow);
  }, [router]);

  const setPage = useCallback(
    (page: number, cursorOverride?: string | null) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("page", String(page));
      // When navigating beyond page CURSOR_THRESHOLD with sort=newest and a cursor is available,
      // pass cursor param so the backend uses keyset (no skip scan).
      if (cursorOverride && page > CURSOR_THRESHOLD && sort === "newest") {
        params.set("cursor", cursorOverride);
      } else {
        params.delete("cursor");
      }
      router.push(`${pathname}?${params}`);
    },
    [router, searchParams, pathname, sort],
  );

  const setVisibility = useCallback(
    (v: VisibilityType | "all") => {
      const params = new URLSearchParams(searchParams.toString());
      if (v === "all") params.delete("visibility");
      else params.set("visibility", v);
      params.delete("page");
      params.delete("cursor");
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
      params.delete("cursor");
      router.push(`${pathname}?${params}`);
    },
    [router, searchParams, pathname],
  );

  const removePlatform = useCallback(
    (platform: string) => {
      const params = new URLSearchParams(searchParams.toString());
      const current = params.get("platforms")?.split(",").filter(Boolean) ?? [];
      const next = current.filter((p) => p !== platform);
      if (next.length) params.set("platforms", next.join(","));
      else params.delete("platforms");
      params.delete("page");
      params.delete("cursor");
      router.push(`${pathname}?${params}`);
    },
    [router, searchParams, pathname],
  );

  const handlePageInputCommit = useCallback(() => {
    const raw = pageInputRef.current?.value ?? "";
    const n = parseInt(raw, 10);
    if (!Number.isInteger(n) || n < 1 || n > data.pages) {
      setPageInputError(true);
      if (pageInputRef.current) pageInputRef.current.value = String(data.page);
      setTimeout(() => setPageInputError(false), 1500);
      return;
    }
    setPageInputError(false);
    setPage(n);
  }, [data.page, data.pages, setPage]);

  const currentVisibility = visibility ?? "all";

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-sm text-muted-foreground">
          {data.total} skill{data.total !== 1 ? "s" : ""}
          {q && (
            <>
              {" "}matching &ldquo;{q}&rdquo;
              <span
                className="ml-1 text-xs text-muted-foreground/70"
                title="Exact name and slug matches rank first"
              >
                (exact name matches rank first)
              </span>
            </>
          )}
          {forkedFrom && (
            <> forked from{" "}
              <span className="font-medium">{forkedFrom.replace("https://github.com/", "")}</span>
            </>
          )}
        </span>
        <div className="ml-auto flex items-center gap-2 flex-wrap">
          {/* Visibility filter */}
          <div className="flex items-center rounded-md border overflow-hidden text-xs">
            {VISIBILITY_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setVisibility(opt.value)}
                className={`px-2.5 py-1 transition-colors ${
                  currentVisibility === opt.value
                    ? "bg-primary text-primary-foreground"
                    : "bg-background hover:bg-muted"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <Suspense fallback={null}>
            <LabelFilter activeLabels={labels} />
          </Suspense>
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
            <PlatformFilter
              activePlatforms={platforms}
              platformCounts={data.platform_counts}
            />
          </Suspense>
          {platforms.map((p) => (
            <button
              key={p}
              onClick={() => removePlatform(p)}
              className="inline-flex items-center gap-1 rounded-full bg-secondary text-secondary-foreground px-2 py-0.5 text-xs hover:bg-secondary/80 transition-colors"
            >
              {p} ×
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
          {labels.length > 0 && platforms.length > 0 ? (
            <>
              <p>No skills match your current filters.</p>
              <Link href="/skills" className="text-primary underline text-sm mt-1 inline-block">
                Clear all filters
              </Link>
            </>
          ) : platforms.length > 0 ? (
            <>
              <p>No skills found for the selected platform(s).</p>
              <p className="text-sm mt-1">Try removing a filter or submitting one.</p>
            </>
          ) : labels.length > 0 ? (
            <>
              <p>No skills match all selected labels.</p>
              <p className="text-sm mt-1">Try removing some to widen your search.</p>
            </>
          ) : (
            <>
              <p>No skills found.</p>
              {q && (
                <Link href="/skills" className="text-primary underline text-sm mt-1 inline-block">
                  Clear search
                </Link>
              )}
            </>
          )}
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {data.items.map((skill) => (
            <SkillCard key={skill.id} skill={skill} accessInstructionsUrl={accessInstructionsUrl} />
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

          {/* Page number input — hidden on narrow viewports (FR-7) */}
          <div className="hidden sm:flex items-center gap-1 text-sm text-muted-foreground">
            <input
              ref={pageInputRef}
              type="number"
              min={1}
              max={data.pages}
              defaultValue={data.page}
              key={data.page}
              onKeyDown={(e) => e.key === "Enter" && handlePageInputCommit()}
              onBlur={() => {
                if (pageInputRef.current?.value !== String(data.page)) handlePageInputCommit();
              }}
              className={`w-14 rounded-md border px-2 py-1 text-center text-sm focus:outline-none focus:ring-2 focus:ring-primary ${
                pageInputError ? "border-destructive ring-destructive" : ""
              }`}
              aria-label="Go to page"
            />
            <span>/ {data.pages}</span>
          </div>

          {/* Compact page indicator on mobile */}
          <span className="sm:hidden text-sm text-muted-foreground">
            {data.page} / {data.pages}
          </span>

          <button
            onClick={() => setPage(data.page + 1, nextCursor)}
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
