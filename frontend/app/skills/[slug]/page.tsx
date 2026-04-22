import { notFound } from "next/navigation";
import { getSkill, getRevisions, listSkills, getSettings } from "@/lib/api";
import { Tombstone } from "@/components/tombstone";
import { SupersededNotice } from "@/components/superseded-notice";
import { ReadmeRender } from "@/components/readme-render";
import { RevisionTimeline } from "@/components/revision-timeline";
import { PlatformBadges } from "@/components/platform-badges";
import { StarRating } from "@/components/star-rating";
import { FlagIndicator } from "@/components/flag-indicator";
import { LabelSection } from "@/components/label-section";
import { formatDate } from "@/lib/utils";
import Link from "next/link";
import { GitFork, Lock } from "lucide-react";

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

  // Fetch forks of this skill in the catalog (FR-P16)
  const [forksData, siteSettings] = await Promise.all([
    listSkills({ forked_from: skill.repo_url, page_size: 3, server: true }),
    getSettings(true),
  ]);
  const forkCount = forksData?.total ?? 0;
  const accessInstructionsUrl = siteSettings.github_access_instructions_url;

  const isInternal = skill.visibility === "internal";

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
            {isInternal && (
              <a
                href={accessInstructionsUrl}
                className="inline-flex items-center gap-1 rounded-full bg-amber-100 text-amber-800 px-2 py-0.5 text-xs font-medium hover:bg-amber-200 transition-colors"
                title="Requires SLAC GitHub access"
              >
                <Lock className="h-3 w-3" />
                SLAC Only
              </a>
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
          <Link
            href={`/skills/${skill.slug}/edit`}
            className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm hover:bg-muted transition-colors"
          >
            Edit
          </Link>
        </div>
      </div>

      {/* SLAC Only info banner */}
      {isInternal && (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <strong>SLAC Only</strong> — This repo requires SLAC GitHub access to clone.{" "}
          <a href={accessInstructionsUrl} className="underline">
            Learn how to get access.
          </a>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main content */}
        <div className="lg:col-span-2 space-y-6">
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

          {/* Labels */}
          <div className="rounded-lg border p-4 space-y-2">
            <h3 className="text-sm font-semibold">Labels</h3>
            <LabelSection slug={skill.slug} initialLabels={skill.labels ?? []} />
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
              <div className="space-y-1">
                <dt className="text-muted-foreground">Repository</dt>
                <dd>
                  <a
                    href={skill.skill_path && skill.skill_path !== "/"
                      ? `${skill.repo_url}/tree/HEAD${skill.skill_path}`
                      : skill.repo_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-mono text-xs break-all hover:underline"
                  >
                    {skill.repo_url.replace("https://github.com/", "")}
                    {skill.skill_path && skill.skill_path !== "/" ? skill.skill_path : ""}
                  </a>
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Updated</dt>
                <dd>{formatDate(skill.updated_at)}</dd>
              </div>
            </dl>
          </div>

          {/* Fork provenance (FR-P8) */}
          {skill.forked_from_url && (
            <div className="rounded-lg border p-4 space-y-1">
              <h3 className="text-sm font-semibold">Fork Provenance</h3>
              <p className="text-sm text-muted-foreground">
                Forked from{" "}
                <a
                  href={skill.forked_from_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium text-foreground underline"
                >
                  {skill.forked_from_url.replace("https://github.com/", "")}
                </a>
              </p>
            </div>
          )}

          {/* Forks in catalog (FR-P16) */}
          {forkCount > 0 && (
            <div className="rounded-lg border p-4 space-y-1">
              <h3 className="text-sm font-semibold">Forks in Catalog</h3>
              <p className="text-sm text-muted-foreground">
                {forkCount} fork{forkCount !== 1 ? "s" : ""} in the catalog.{" "}
                <Link
                  href={`/skills?forked_from=${encodeURIComponent(skill.repo_url)}`}
                  className="text-primary underline"
                >
                  View all
                </Link>
              </p>
            </div>
          )}

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
                Uses S3DF AI Gateway for Experimentalists
              </span>
            </div>
          )}

          {/* Revision History */}
          <div className="rounded-lg border p-4">
            <h3 className="text-sm font-semibold mb-3">Revision History</h3>
            <RevisionTimeline revisions={revisions} />
          </div>
        </div>
      </div>
    </div>
  );
}
