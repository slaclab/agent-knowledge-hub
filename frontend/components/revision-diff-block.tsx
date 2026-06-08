"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, TriangleAlert } from "lucide-react";
import type { FieldDiff } from "@/types/skill";
import { SIGNIFICANT_FIELDS } from "@/lib/revision-diff";

const FIELD_LABELS: Record<string, string> = {
  name: "Name",
  description: "Description",
  version: "Version",
  license: "License",
  repo_url: "Repo URL",
  forked_from_url: "Forked from URL",
  visibility: "Visibility",
  labels: "Labels",
  compatible_platforms: "Platforms",
  github_stars: "GitHub Stars",
  last_commit_at: "Last Commit",
};

const TRUNCATE = 120;

function truncate(s: string | number | null): string {
  if (s == null) return "—";
  const str = String(s);
  return str.length > TRUNCATE ? str.slice(0, TRUNCATE) + "…" : str;
}

interface RevisionDiffBlockProps {
  diffs: FieldDiff[];
}

export function RevisionDiffBlock({ diffs }: RevisionDiffBlockProps) {
  const [open, setOpen] = useState(false);

  const meaningful = diffs.filter((d) => d.type !== "readme_updated");
  const hasReadme = diffs.some((d) => d.type === "readme_updated");

  if (meaningful.length === 0 && !hasReadme) return null;

  const label =
    meaningful.length === 0
      ? null
      : `${meaningful.length} field${meaningful.length !== 1 ? "s" : ""} changed`;

  return (
    <div className="mt-1">
      <div className="flex items-center gap-2 flex-wrap">
        {label && (
          <button
            onClick={() => setOpen((o) => !o)}
            className="inline-flex items-center gap-1 text-xs text-muted-foreground border rounded px-1.5 py-0.5 hover:bg-muted transition-colors"
            aria-expanded={open}
          >
            {open ? (
              <ChevronDown className="h-3 w-3" aria-hidden />
            ) : (
              <ChevronRight className="h-3 w-3" aria-hidden />
            )}
            {label}
          </button>
        )}
        {hasReadme && (
          <span className="text-xs text-muted-foreground italic">README updated</span>
        )}
      </div>

      {open && meaningful.length > 0 && (
        <div className="mt-2 space-y-2 text-xs">
          {meaningful.map((diff) => {
            const isSignificant = SIGNIFICANT_FIELDS.has(diff.field);
            const fieldLabel = FIELD_LABELS[diff.field] ?? diff.field;

            return (
              <div
                key={diff.field}
                className={`space-y-0.5 ${isSignificant ? "rounded border border-amber-200 bg-amber-50 px-2 py-1" : ""}`}
              >
                <div className="flex items-center gap-1 font-medium text-foreground">
                  {isSignificant && (
                    <TriangleAlert className="h-3 w-3 text-amber-600" aria-hidden />
                  )}
                  {fieldLabel}
                </div>

                {diff.type === "scalar" && (
                  <div className="space-y-0.5">
                    {diff.old != null && (
                      <div className="text-red-700 line-through break-all">{truncate(diff.old)}</div>
                    )}
                    {diff.new != null && (
                      <div className="text-green-700 break-all">{truncate(diff.new)}</div>
                    )}
                    {diff.old == null && diff.new == null && (
                      <div className="text-muted-foreground">—</div>
                    )}
                  </div>
                )}

                {diff.type === "array" && (
                  <div className="flex flex-wrap gap-1">
                    {diff.removed.map((item) => (
                      <span
                        key={`rm-${item}`}
                        className="inline-flex items-center gap-0.5 rounded-full bg-red-100 text-red-700 px-1.5 py-0.5 line-through"
                        aria-label={`removed: ${item}`}
                      >
                        <span aria-hidden>−</span> {item}
                      </span>
                    ))}
                    {diff.added.map((item) => (
                      <span
                        key={`add-${item}`}
                        className="inline-flex items-center gap-0.5 rounded-full bg-green-100 text-green-700 px-1.5 py-0.5"
                        aria-label={`added: ${item}`}
                      >
                        <span aria-hidden>+</span> {item}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
