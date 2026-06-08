import { cn } from "@/lib/utils";
import type { Skill } from "@/types/skill";
import Link from "next/link";
import { GitFork, ArrowRight, Lock } from "lucide-react";
import { platformPillClass } from "@/components/platform-badges";
import { labelColor } from "@/lib/label-color";
import { StarRating } from "./star-rating";
import { FlagIndicator } from "./flag-indicator";

interface SkillCardProps {
  skill: Skill;
  accessInstructionsUrl?: string;
}

export function SkillCard({ skill, accessInstructionsUrl = "/guides/slac-github-access" }: SkillCardProps) {
  const isDeactivated = skill.status === "deactivated";
  const isSuperseded = !!skill.superseded_by_slug;
  const isInternal = skill.visibility === "internal";
  const labels = skill.labels ?? [];
  const visibleLabels = labels.slice(0, 5);
  const overflowCount = labels.length - visibleLabels.length;

  return (
    <Link
      href={`/skills/${skill.slug}`}
      className={cn(
        "block rounded-lg border bg-card text-card-foreground shadow-sm hover:shadow-md transition-shadow p-3.5",
        isDeactivated && "opacity-60",
      )}
    >
      <div className="flex items-center gap-2 flex-wrap">
        <h3 className="font-semibold text-base leading-tight truncate">{skill.name}</h3>
        {skill.entry_type === "marketplace_ref" && (
          <span className="inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium">
            ref
          </span>
        )}
        {isInternal && (
          <a
            href={accessInstructionsUrl}
            onClick={(e) => e.stopPropagation()}
            className="inline-flex items-center gap-1 rounded-full bg-amber-100 text-amber-800 px-2 py-0.5 text-xs font-medium hover:bg-amber-200 transition-colors"
            title="Requires SLAC GitHub access"
          >
            <Lock className="h-3 w-3" />
            SLAC Only
          </a>
        )}
        {isDeactivated && (
          <span className="inline-flex items-center rounded-full bg-destructive/10 text-destructive px-2 py-0.5 text-xs font-medium">
            deactivated
          </span>
        )}
        {isSuperseded && (
          <span className="inline-flex items-center gap-1 rounded-full bg-yellow-100 text-yellow-800 px-2 py-0.5 text-xs font-medium">
            <ArrowRight className="h-3 w-3" />
            superseded
          </span>
        )}
        <FlagIndicator count={skill.flag_count} />
        {skill.update_available && (
          <span
            className="inline-flex items-center rounded-full bg-sky-100 text-sky-800 px-2 py-0.5 text-xs font-medium"
            title="A newer version is available upstream"
          >
            Update available
          </span>
        )}
        {skill.rating_count > 0 && (
          <span className="ml-auto">
            <StarRating value={skill.avg_rating} count={skill.rating_count} readonly />
          </span>
        )}
      </div>
      {skill.description && (
        <p className="mt-1 text-sm text-muted-foreground line-clamp-3">{skill.description}</p>
      )}
      {skill.forked_from_url && (
        <p className="mt-1 text-xs text-muted-foreground">
          Fork of{" "}
          <a
            href={skill.forked_from_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="underline hover:text-foreground"
          >
            {skill.forked_from_url.replace("https://github.com/", "")}
          </a>
        </p>
      )}
      {(visibleLabels.length > 0 || skill.compatible_platforms.length > 0 || skill.uses_agent_gateway) && (
        <div className="mt-1.5 flex items-center gap-1 flex-nowrap overflow-hidden">
          <div className="flex items-center gap-1 flex-nowrap overflow-hidden flex-1 min-w-0">
            {visibleLabels.map((label) => (
              <Link
                key={label.name}
                href={`/skills?labels=${encodeURIComponent(label.name)}`}
                onClick={(e) => e.stopPropagation()}
                className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium cursor-pointer hover:opacity-80 transition-opacity flex-shrink-0 ${labelColor(label.name)}`}
              >
                {label.name}
              </Link>
            ))}
            {overflowCount > 0 && (
              <span className="inline-flex items-center rounded-full border px-2 py-0.5 text-xs text-muted-foreground flex-shrink-0">
                +{overflowCount} more
              </span>
            )}
          </div>
          <div className="flex items-center gap-1 flex-shrink-0 ml-auto">
            {skill.has_mcp_server && (
              <span className="inline-flex items-center rounded-full bg-violet-100 text-violet-800 px-2 py-0.5 text-xs font-medium">MCP</span>
            )}
            {skill.agent_count > 0 && (
              <span className="inline-flex items-center rounded-full bg-indigo-100 text-indigo-800 px-2 py-0.5 text-xs font-medium">
                {skill.agent_count} agent{skill.agent_count !== 1 ? "s" : ""}
              </span>
            )}
            {skill.uses_agent_gateway && (
              <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 text-blue-800 px-2 py-0.5 text-xs font-medium">
                <GitFork className="h-3 w-3" />
                AI Gateway
              </span>
            )}
            {skill.compatible_platforms.map((p) => (
              <Link
                key={p}
                href={`/skills?platforms=${encodeURIComponent(p)}`}
                onClick={(e) => e.stopPropagation()}
                className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium cursor-pointer hover:opacity-80 transition-opacity ${platformPillClass(p, true)}`}
              >
                {p}
              </Link>
            ))}
          </div>
        </div>
      )}
    </Link>
  );
}
