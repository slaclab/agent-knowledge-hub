import Link from "next/link";
import type { SkillsetListOut } from "@/types/skillset";

export function SkillsetCard({ skillset }: { skillset: SkillsetListOut }) {
  const count = skillset.member_count;
  return (
    <Link
      href={`/skillsets/${skillset.slug}`}
      className="block rounded-lg border bg-card text-card-foreground shadow-sm hover:shadow-md transition-shadow p-3.5"
    >
      <h3 className="font-semibold text-base leading-tight truncate">{skillset.name}</h3>
      {skillset.description && (
        <p className="mt-1 text-sm text-muted-foreground line-clamp-3">{skillset.description}</p>
      )}
      <p className="mt-1.5 text-xs text-muted-foreground">
        {count} skill{count !== 1 ? "s" : ""} · curated by {skillset.created_by}
      </p>
    </Link>
  );
}
