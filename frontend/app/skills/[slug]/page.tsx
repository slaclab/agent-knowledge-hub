import { notFound } from "next/navigation";
import { getSkill, getRevisions } from "@/lib/api";
import { Tombstone } from "@/components/tombstone";
import { SupersededNotice } from "@/components/superseded-notice";
import { ReadmeRender } from "@/components/readme-render";
import { RevisionTimeline } from "@/components/revision-timeline";
import { PlatformBadges } from "@/components/platform-badges";
import { StarRating } from "@/components/star-rating";
import { FlagIndicator } from "@/components/flag-indicator";
import { formatDate } from "@/lib/utils";
import Link from "next/link";
import { ExternalLink, GitFork, RefreshCw } from "lucide-react";

interface PageProps {
  params: { slug: string };
}

export default async function SkillDetailPage({ params }: PageProps) {
  const { skill, deactivated, reason } = await getSkill(params.slug, true);

  if (deactivated) {
    return (
      <div className="max-w-2xl mx-auto py-8">
        <Tombstone reason={reason} />
      </div>
    );
  }

  if (!skill) return notFound();

  const revisions = await getRevisions(params.slug, true);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Superseded notice */}
      {skill.superseded_by_slug && (
        <SupersededNotice slug={skill.superseded_by_slug} />
      )}

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-3xl font-bold">{skill.name}</h1>
            {skill.entry_type === "marketplace_ref" && (
              <span className="rounded-full border px-2 py-0.5 text-xs">ref</span>
            )}
            <FlagIndicator count={skill.flag_count} />
          </div>
          {skill.description && (
            <p className="text-muted-foreground">{skill.description}</p>
          )}
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span>by {skill.submitter_id}</span>
            <span>submitted {formatDate(skill.submitted_at)}</span>
          </div>
        </div>
        <div className="flex flex-col items-end gap-2">
          <a
            href={skill.repo_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm hover:bg-muted transition-colors"
          >
            <ExternalLink className="h-4 w-4" />
            View on GitHub
          </a>
          {/* Edit button (shown to all; auth check is client-side in edit page) */}
          <Link
            href={`/skills/${skill.slug}/edit`}
            className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm hover:bg-muted transition-colors"
          >
            Edit
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Tabs: Overview / Revisions */}
          <div className="space-y-4">
            {skill.readme_html ? (
              <div className="rounded-lg border p-6">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-4">
                  README
                </h2>
                <ReadmeRender html={skill.readme_html} />
              </div>
            ) : (
              <div className="rounded-lg border p-6 text-center text-muted-foreground text-sm">
                No README available.
              </div>
            )}

            <div className="rounded-lg border p-6">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-4">
                Revision History
              </h2>
              <RevisionTimeline revisions={revisions} />
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          {/* Ratings */}
          <div className="rounded-lg border p-4 space-y-2">
            <h3 className="text-sm font-semibold">Rating</h3>
            <StarRating value={skill.avg_rating} count={skill.rating_count} />
            <p className="text-xs text-muted-foreground">
              Rating submission coming soon.
            </p>
          </div>

          {/* Metadata */}
          <div className="rounded-lg border p-4 space-y-3">
            <h3 className="text-sm font-semibold">Details</h3>
            <dl className="space-y-2 text-sm">
              {skill.version && (
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Version</dt>
                  <dd className="font-mono">{skill.version}</dd>
                </div>
              )}
              {skill.license && (
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">License</dt>
                  <dd>{skill.license}</dd>
                </div>
              )}
              {skill.github_stars !== null && (
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">GitHub Stars</dt>
                  <dd>{skill.github_stars.toLocaleString()}</dd>
                </div>
              )}
              {skill.last_commit_at && (
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Last Commit</dt>
                  <dd>{formatDate(skill.last_commit_at)}</dd>
                </div>
              )}
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Updated</dt>
                <dd>{formatDate(skill.updated_at)}</dd>
              </div>
            </dl>
          </div>

          {/* Platforms */}
          {skill.compatible_platforms.length > 0 && (
            <div className="rounded-lg border p-4 space-y-2">
              <h3 className="text-sm font-semibold">Compatible Platforms</h3>
              <PlatformBadges platforms={skill.compatible_platforms} />
            </div>
          )}

          {/* Agent Gateway badge */}
          {skill.uses_agent_gateway && (
            <div className="rounded-lg border p-4">
              <span className="inline-flex items-center gap-1.5 text-sm text-blue-800">
                <GitFork className="h-4 w-4" />
                Uses SLAC Agent Gateway
              </span>
            </div>
          )}

          {/* Labels (stub) */}
          <div className="rounded-lg border p-4 space-y-2">
            <h3 className="text-sm font-semibold">Labels</h3>
            <p className="text-xs text-muted-foreground">Label support coming soon.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
