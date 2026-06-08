"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Github, Star } from "lucide-react";
import Link from "next/link";
import type { ProvenanceNode, ProvenanceTree } from "@/types/provenance";
import { formatDate } from "@/lib/utils";

interface ProvenanceTreeProps {
  tree: ProvenanceTree;
  forkedFromUrl: string | null;
  repoUrl: string;
}

function NodeCard({ node, depth = 0 }: { node: ProvenanceNode; depth?: number }) {
  const isRedacted = !node.slug && node.in_catalog;
  const isExternal = !node.in_catalog;

  return (
    <div
      className="relative pl-4 border-l border-border"
      style={{ marginLeft: depth > 0 ? "0.75rem" : 0 }}
    >
      <div className="py-1">
        {isRedacted ? (
          <span className="text-sm text-muted-foreground italic">[internal skill]</span>
        ) : isExternal ? (
          <div className="flex flex-wrap items-center gap-2">
            <a
              href={node.repo_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-sm hover:underline font-medium"
            >
              <Github className="h-3 w-3 shrink-0" aria-label="External GitHub repo" />
              <span>{node.repo_url.replace("https://github.com/", "")}</span>
            </a>
            {node.github_stars != null && (
              <span className="flex items-center gap-0.5 text-xs text-muted-foreground">
                <Star className="h-3 w-3" />
                {node.github_stars.toLocaleString()}
              </span>
            )}
            {node.last_commit_at && (
              <span className="text-xs text-muted-foreground">last commit {formatDate(node.last_commit_at)}</span>
            )}
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href={`/skills/${node.slug}`}
              className="text-sm font-medium hover:underline"
            >
              {node.name}
            </Link>
            {node.status === "deactivated" && (
              <span className="text-xs rounded-full bg-muted px-1.5 py-0.5 text-muted-foreground">deactivated</span>
            )}
            <div className="flex flex-wrap items-center gap-2 sm:flex-row sm:items-center flex-col items-start">
              {node.github_stars != null && (
                <span className="flex items-center gap-0.5 text-xs text-muted-foreground">
                  <Star className="h-3 w-3" />
                  {node.github_stars.toLocaleString()}
                </span>
              )}
              {node.avg_rating != null && (
                <span className="text-xs text-muted-foreground">⭐ {node.avg_rating.toFixed(1)}</span>
              )}
              {node.last_commit_at && (
                <span className="text-xs text-muted-foreground">last commit {formatDate(node.last_commit_at)}</span>
              )}
              {node.submitter_id && (
                <span className="text-xs text-muted-foreground">
                  by{" "}
                  <Link href={`/users/${encodeURIComponent(node.submitter_id)}`} className="hover:underline">
                    {node.submitter_id}
                  </Link>
                </span>
              )}
            </div>
          </div>
        )}
      </div>
      {node.forks.slice(0, 5).map((fork) => (
        <NodeCard key={fork.slug ?? fork.repo_url} node={fork} depth={depth + 1} />
      ))}
    </div>
  );
}

export function ProvenanceTreeView({ tree, forkedFromUrl, repoUrl }: ProvenanceTreeProps) {
  const [open, setOpen] = useState(false);

  if (tree.empty) return null;

  // Build adaptive collapsed summary (FR-9): only show segments that exist
  // Supersession is intentionally excluded from the summary (banner handles it)
  const summaryParts: string[] = [];
  if (tree.upstream.length > 0) {
    const first = tree.upstream[0];
    const upstreamName = first.in_catalog && first.slug ? first.name : (first.repo_url.replace("https://github.com/", "") || first.name);
    summaryParts.push(`Forked from ${upstreamName}`);
  }
  if (tree.subject && tree.subject.total_fork_count > 0) {
    summaryParts.push(`${tree.subject.total_fork_count} fork${tree.subject.total_fork_count !== 1 ? "s" : ""} in catalog`);
  }
  const collapsedSummary = summaryParts.join(" · ");

  const subject = tree.subject;
  const forks = subject?.forks ?? [];
  const displayForks = forks.slice(0, 5);
  const overflowCount = (subject?.total_fork_count ?? 0) - displayForks.length;

  return (
    <div className="rounded-lg border p-4 space-y-2">
      <button
        className="flex items-center gap-1.5 w-full text-left"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        {open ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
        )}
        <span className="text-sm font-semibold">Provenance</span>
        {!open && collapsedSummary && (
          <span className="text-xs text-muted-foreground ml-1 truncate">{collapsedSummary}</span>
        )}
      </button>

      {open && (
        <div className="space-y-3 mt-1">
          {tree.upstream.length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">Upstream</p>
              <div className="space-y-0">
                {tree.upstream.map((node, i) => (
                  <NodeCard key={node.slug ?? node.repo_url ?? i} node={node} />
                ))}
              </div>
            </div>
          )}

          {subject && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">This skill</p>
              <NodeCard node={{ ...subject, forks: [] }} />
            </div>
          )}

          {displayForks.length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">
                Forks in catalog ({subject?.total_fork_count ?? 0})
              </p>
              <div className="space-y-0">
                {displayForks.map((fork) => (
                  <NodeCard key={fork.slug ?? fork.repo_url} node={fork} />
                ))}
              </div>
              {overflowCount > 0 && (
                <Link
                  href={`/skills?forked_from=${encodeURIComponent(repoUrl)}`}
                  className="text-xs text-primary hover:underline mt-1 inline-block"
                >
                  and {overflowCount} more fork{overflowCount !== 1 ? "s" : ""} →
                </Link>
              )}
            </div>
          )}

          {tree.supersession.length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">Superseded by</p>
              <div className="flex flex-wrap items-center gap-1">
                {tree.supersession.map((node, i) => (
                  <span key={node.slug ?? i} className="flex items-center gap-1">
                    {i > 0 && <span className="text-muted-foreground">→</span>}
                    {node.slug ? (
                      <Link href={`/skills/${node.slug}`} className="text-sm hover:underline">
                        {node.name}
                      </Link>
                    ) : (
                      <span className="text-sm text-muted-foreground italic">[internal skill]</span>
                    )}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
