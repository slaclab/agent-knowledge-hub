import { notFound } from "next/navigation";
import { headers } from "next/headers";
import { getSkill, getRevisions, getProvenance, getSettings, getMe } from "@/lib/api";
import { Tombstone } from "@/components/tombstone";
import { SupersededNotice } from "@/components/superseded-notice";
import { SkillContentTabs } from "@/components/skill-content-tabs";
import { RevisionTimeline } from "@/components/revision-timeline";
import { PlatformSection } from "@/components/platform-section";
import { FlagIndicator } from "@/components/flag-indicator";
import { FlagButton } from "@/components/flag-button";
import { AdminDeactivateButton } from "@/components/admin-deactivate-button";
import { LabelSection } from "@/components/label-section";
import { RatingWidget } from "@/components/rating-widget";
import { ProvenanceTreeView } from "@/components/provenance-tree";
import { formatDate } from "@/lib/utils";
import Link from "next/link";
import { GitFork, Lock } from "lucide-react";
import { DeleteSkillButton } from "@/components/delete-skill-button";
import { PinSkillButton } from "@/components/pin-skill-button";

interface PageProps {
  params: { slug: string };
}

export default async function SkillDetailPage({ params }: PageProps) {
  const h = headers();
  const viewer =
    h.get(process.env.AUTH_USER_HEADER ?? "x-auth-request-user") ||
    h.get("x-vouch-idp-claims-name") ||
    h.get("x-vouch-user") ||
    h.get("x-forwarded-user");
  const { skill, deactivated, reason, superseded_by_slug } = await getSkill(params.slug, true, viewer ?? undefined);

  if (deactivated) {
    return (
      <div className="max-w-2xl mx-auto py-8">
        <Tombstone reason={reason} superseded_by_slug={superseded_by_slug} />
      </div>
    );
  }

  if (!skill) return notFound();

  const revisions = await getRevisions(params.slug, true);

  const [provenanceData, siteSettings, me] = await Promise.all([
    getProvenance(params.slug, true),
    getSettings(true),
    getMe(true),
  ]);
  const isAdmin = me?.is_admin ?? false;
  const accessInstructionsUrl = siteSettings.github_access_instructions_url;

  // Unique contributors in order of first appearance; submitter always first
  const contributors = [
    skill.submitter_id,
    ...revisions.map((r) => r.actor_id).filter((id) => id !== skill.submitter_id),
  ].filter((id, i, arr) => arr.indexOf(id) === i);

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
            <FlagIndicator
              count={skill.flag_count}
              isMine={skill.my_flag?.status === "active"}
            />
          </div>
          {skill.description && (
            <p className="text-muted-foreground">{skill.description}</p>
          )}
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span>
              by{" "}
              {contributors.map((c, i) => (
                <span key={c}>
                  {i > 0 && ", "}
                  <Link
                    href={`/users/${encodeURIComponent(c)}`}
                    className="hover:text-foreground hover:underline"
                  >
                    {c}
                  </Link>
                </span>
              ))}
            </span>
            <span>submitted {formatDate(skill.submitted_at)}</span>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <FlagButton
            skillSlug={skill.slug}
            initialFlagCount={skill.flag_count}
            myFlag={skill.my_flag ?? null}
            isAuthenticated={!!viewer}
          />
          {isAdmin && (
            <AdminDeactivateButton slug={skill.slug} />
          )}
          <Link
            href={`/skills/${skill.slug}/edit`}
            className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm hover:bg-muted transition-colors"
          >
            Edit
          </Link>
          <DeleteSkillButton slug={skill.slug} submitterId={skill.submitter_id} />
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
          <SkillContentTabs
            readmeRaw={skill.readme_raw}
            readmeHtml={skill.readme_html}
            skillMdRaw={skill.skill_md_raw}
            skillMdFilename={skill.skill_md_filename}
            isInternal={isInternal}
            isAuthenticated={!!viewer}
            fileManifest={skill.file_manifest ?? []}
            manifestTruncated={skill.manifest_truncated ?? false}
            slug={params.slug}
          />
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          {/* Details (merged with Plugin Info + Author) */}
          <div className="rounded-lg border p-4 space-y-3">
            <h3 className="text-sm font-semibold">Details</h3>
            <dl className="space-y-2 text-sm">
              {skill.plugin_author && (
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Author</dt>
                  <dd>{skill.plugin_author}</dd>
                </div>
              )}
              {skill.version && (
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Declared version</dt>
                  <dd className="font-mono">{skill.version}</dd>
                </div>
              )}
              {(skill.pinned_ref || skill.pinned_commit_sha) && (
                <div className="flex justify-between items-start">
                  <dt className="text-muted-foreground">Pinned git tag</dt>
                  <dd className="text-right">
                    {skill.pinned_ref && (
                      <span className="font-mono text-xs">{skill.pinned_ref}</span>
                    )}
                    {skill.pinned_commit_sha && (
                      <span className="block font-mono text-xs text-muted-foreground">
                        {skill.pinned_commit_sha.slice(0, 7)}
                      </span>
                    )}
                  </dd>
                </div>
              )}
              {skill.update_available && (
                <div className="rounded-md bg-sky-50 border border-sky-200 px-3 py-2 space-y-1.5">
                  <p className="text-xs text-sky-800">
                    A newer version is available upstream.
                    {viewer
                      ? null
                      : " Contact the skill submitter or an admin to update."}
                  </p>
                  {viewer && (viewer === skill.submitter_id || isAdmin) && (
                    <PinSkillButton slug={skill.slug} />
                  )}
                  {viewer && viewer !== skill.submitter_id && !isAdmin && (
                    <p className="text-xs text-sky-700">
                      Only the submitter (<span className="font-medium">{skill.submitter_id}</span>) or an admin can update.
                    </p>
                  )}
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
              {(skill.has_mcp_server || skill.agent_count > 0 || skill.has_scripts) && (
                <div className="flex justify-between items-start">
                  <dt className="text-muted-foreground">Components</dt>
                  <dd className="flex flex-wrap justify-end gap-1">
                    {skill.has_mcp_server && (
                      <span className="rounded-full bg-violet-100 text-violet-800 px-2 py-0.5 text-xs font-medium">MCP server</span>
                    )}
                    {skill.agent_count > 0 && (
                      <span className="rounded-full bg-indigo-100 text-indigo-800 px-2 py-0.5 text-xs font-medium">
                        {skill.agent_count} agent{skill.agent_count !== 1 ? "s" : ""}
                      </span>
                    )}
                    {skill.has_scripts && (
                      <span className="rounded-full bg-orange-100 text-orange-800 px-2 py-0.5 text-xs font-medium">scripts</span>
                    )}
                  </dd>
                </div>
              )}
            </dl>
          </div>

          {/* Ratings */}
          <div className="rounded-lg border p-4 space-y-2">
            <h3 className="text-sm font-semibold">Rating</h3>
            <RatingWidget
              slug={skill.slug}
              initialAvgRating={skill.avg_rating}
              initialRatingCount={skill.rating_count}
            />
          </div>

          {/* Labels */}
          <div className="rounded-lg border p-4 space-y-2">
            <h3 className="text-sm font-semibold">Labels</h3>
            <LabelSection slug={skill.slug} initialLabels={skill.labels ?? []} />
          </div>

          {/* Provenance tree (#014) */}
          {provenanceData && !provenanceData.empty && (
            <ProvenanceTreeView
              tree={provenanceData}
              forkedFromUrl={skill.forked_from_url}
              repoUrl={skill.repo_url}
            />
          )}

          {/* Platforms */}
          <div className="rounded-lg border p-4 space-y-2">
            <h3 className="text-sm font-semibold">Compatible Platforms</h3>
            <PlatformSection slug={skill.slug} initialPlatforms={skill.compatible_platforms} />
          </div>

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
