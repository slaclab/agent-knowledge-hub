import type { SkillRevision } from "@/types/skill";
import { formatDate } from "@/lib/utils";
import { GitCommitHorizontal } from "lucide-react";

const ACTION_LABELS: Record<SkillRevision["action"], string> = {
  create: "Submitted",
  edit: "Edited",
  refetch: "Re-fetched from GitHub",
  deactivate: "Deactivated",
  reactivate: "Reactivated",
  pin: "Pinned to latest",
};

interface RevisionTimelineProps {
  revisions: SkillRevision[];
}

export function RevisionTimeline({ revisions }: RevisionTimelineProps) {
  if (revisions.length === 0) {
    return <p className="text-sm text-muted-foreground">No revision history available.</p>;
  }

  return (
    <ol className="relative border-l border-border space-y-6 ml-3">
      {revisions.map((rev) => (
        <li key={rev.id} className="ml-6">
          <span className="absolute -left-3 flex h-6 w-6 items-center justify-center rounded-full bg-background border border-border">
            <GitCommitHorizontal className="h-3 w-3 text-muted-foreground" />
          </span>
          <div className="space-y-0.5">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-medium text-sm">{ACTION_LABELS[rev.action] ?? rev.action}</span>
              <span className="text-xs text-muted-foreground">by {rev.actor_id}</span>
              <span className="text-xs text-muted-foreground">·</span>
              <time className="text-xs text-muted-foreground">{formatDate(rev.created_at)}</time>
              <span className="text-xs text-muted-foreground rounded-full border px-1.5">
                rev {rev.revision_number}
              </span>
            </div>
            {rev.changelog_note && (
              <p className="text-sm text-muted-foreground italic">{rev.changelog_note}</p>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
