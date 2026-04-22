import { listSkills, getSettings } from "@/lib/api";
import { SkillList } from "@/components/skill-list";
import type { SortOption, VisibilityType } from "@/types/skill";
import { Suspense } from "react";

interface PageProps {
  searchParams: {
    q?: string;
    labels?: string;
    sort?: string;
    page?: string;
    forked_from?: string;
    visibility?: string;
  };
}

export default async function SkillsPage({ searchParams }: PageProps) {
  const q = searchParams.q ?? "";
  const labels = searchParams.labels ? searchParams.labels.split(",").filter(Boolean) : [];
  const sort = (searchParams.sort as SortOption) ?? "newest";
  const page = Number(searchParams.page ?? 1);
  const forkedFrom = searchParams.forked_from;
  const visibility = searchParams.visibility as VisibilityType | "all" | undefined;

  const [data, siteSettings] = await Promise.all([
    listSkills({
      q, labels, sort, page, page_size: 20, server: true,
      forked_from: forkedFrom,
      visibility: visibility !== "all" ? visibility : undefined,
    }),
    getSettings(true),
  ]);

  if (!data) {
    return (
      <div className="text-center py-16 text-muted-foreground">
        <p>Failed to load skills. The backend may be unavailable.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Skill Catalog</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Discover agent skills and plugins built by the SLAC community.
          </p>
        </div>
      </div>
      <Suspense fallback={<div className="text-sm text-muted-foreground">Loading…</div>}>
        <SkillList
          data={data}
          sort={sort}
          q={q}
          labels={labels}
          forkedFrom={forkedFrom}
          visibility={visibility}
          accessInstructionsUrl={siteSettings.github_access_instructions_url}
        />
      </Suspense>
    </div>
  );
}
