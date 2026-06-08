"use client";

import { useState } from "react";
import type { SkillRevision } from "@/types/skill";
import { computeDiff, computeGenesis } from "@/lib/revision-diff";
import { RevisionDiffBlock } from "@/components/revision-diff-block";
import { formatDate } from "@/lib/utils";
import { GitCommitHorizontal } from "lucide-react";
import Link from "next/link";

const ACTION_LABELS: Record<SkillRevision["action"], string> = {
  create: "Submitted",
  edit: "Edited",
  refetch: "Re-fetched from GitHub",
  deactivate: "Deactivated",
  reactivate: "Reactivated",
  pin: "Pinned to latest",
};

const MAX_VISIBLE = 10;

interface RevisionTimelineProps {
  revisions: SkillRevision[];
}

export function RevisionTimeline({ revisions }: RevisionTimelineProps) {
  const [showAll, setShowAll] = useState(false);

  if (revisions.length === 0) {
    return <p className="text-sm text-muted-foreground">No revision history available.</p>;
  }

  const sorted = [...revisions].sort((a, b) => a.revision_number - b.revision_number);
  const visible = showAll ? sorted : sorted.slice(-MAX_VISIBLE);
  const hidden = sorted.length - visible.length;

  return (
    <div className="space-y-3">
      {hidden > 0 && (
        <button
          onClick={() => setShowAll(true)}
          className="text-xs text-primary hover:underline"
        >
          Show all {sorted.length} revisions
        </button>
      )}
      <ol className="relative border-l border-border space-y-6 ml-3">
        {visible.map((rev, idx) => {
          const prevRev = sorted[sorted.indexOf(rev) - 1];
          const diffs =
            rev.action === "create"
              ? computeGenesis(rev.snapshot as Record<string, unknown>)
              : ["edit", "refetch", "pin"].includes(rev.action) && prevRev
              ? computeDiff(
                  prevRev.snapshot as Record<string, unknown>,
                  rev.snapshot as Record<string, unknown>,
                )
              : [];

          const isEmptyRefetch =
            rev.action === "refetch" &&
            diffs.length === 0;

          return (
            <li key={rev.revision_number} className="ml-6">
              <span className="absolute -left-3 flex h-6 w-6 items-center justify-center rounded-full bg-background border border-border">
                <GitCommitHorizontal className="h-3 w-3 text-muted-foreground" />
              </span>
              <div className="space-y-0.5">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-sm">{ACTION_LABELS[rev.action] ?? rev.action}</span>
                  <Link
                    href={`/users/${encodeURIComponent(rev.actor_id)}`}
                    className="text-xs text-muted-foreground hover:text-foreground hover:underline"
                  >
                    by {rev.actor_id}
                  </Link>
                  <span className="text-xs text-muted-foreground">·</span>
                  <time className="text-xs text-muted-foreground">{formatDate(rev.created_at)}</time>
                  <span className="text-xs text-muted-foreground rounded-full border px-1.5">
                    rev {rev.revision_number}
                  </span>
                </div>
                {rev.changelog_note && (
                  <p className="text-sm text-muted-foreground italic">{rev.changelog_note}</p>
                )}
                {isEmptyRefetch ? (
                  <p className="text-xs text-muted-foreground italic mt-1">Re-fetched — no changes detected</p>
                ) : diffs.length > 0 ? (
                  <RevisionDiffBlock diffs={diffs} />
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
