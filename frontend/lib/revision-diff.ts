import type { FieldDiff } from "@/types/skill";

const SEMANTIC_FIELDS = [
  "name",
  "description",
  "version",
  "license",
  "repo_url",
  "forked_from_url",
  "visibility",
  "labels",
] as const;

const ARRAY_FIELDS = new Set(["compatible_platforms", "labels"]);

const METADATA_FIELDS = ["github_stars", "last_commit_at"] as const;

export const SIGNIFICANT_FIELDS = new Set(["repo_url", "forked_from_url"]);

const EXCLUDED_FIELDS = new Set([
  "snapshotted_files",
  "readme_html",
  "readme_raw",
  "skill_md_raw",
  "file_manifest",
]);

const ALL_DIFFABLE = [
  ...SEMANTIC_FIELDS,
  "compatible_platforms",
  ...METADATA_FIELDS,
] as const;

function normalizeArray(v: unknown): string[] {
  if (v == null) return [];
  if (Array.isArray(v)) return v.map(String);
  return [];
}

function normalizeScalar(v: unknown): string | number | null {
  if (v == null) return null;
  if (typeof v === "string" || typeof v === "number") return v;
  return String(v);
}

export function computeDiff(
  prev: Record<string, unknown>,
  next: Record<string, unknown>,
): FieldDiff[] {
  const diffs: FieldDiff[] = [];

  for (const field of ALL_DIFFABLE) {
    if (EXCLUDED_FIELDS.has(field)) continue;

    const prevVal = prev[field];
    const nextVal = next[field];

    if (ARRAY_FIELDS.has(field)) {
      // Skip if the field is absent in BOTH snapshots (legacy snapshot)
      if (!(field in prev) && !(field in next)) continue;
      const pArr = normalizeArray(prevVal);
      const nArr = normalizeArray(nextVal);
      const pSet = new Set(pArr);
      const nSet = new Set(nArr);
      const added = nArr.filter((x) => !pSet.has(x));
      const removed = pArr.filter((x) => !nSet.has(x));
      if (added.length > 0 || removed.length > 0) {
        diffs.push({ field, type: "array", added, removed });
      }
    } else {
      const pScalar = normalizeScalar(prevVal);
      const nScalar = normalizeScalar(nextVal);
      if (pScalar !== nScalar) {
        diffs.push({ field, type: "scalar", old: pScalar, new: nScalar });
      }
    }
  }

  // README updated indicator (not a full diff entry)
  if (prev["readme_html"] !== next["readme_html"] && next["readme_html"] != null) {
    diffs.push({ field: "readme_html", type: "readme_updated" });
  }

  return diffs;
}

/**
 * Compute the genesis display for a `create` revision — show initial values
 * as "added" for the meaningful semantic fields.
 */
export function computeGenesis(snapshot: Record<string, unknown>): FieldDiff[] {
  const diffs: FieldDiff[] = [];
  const empty: Record<string, unknown> = {};
  // Treat creation as diff from empty → snapshot
  return computeDiff(empty, snapshot).filter(
    (d) => d.type !== "readme_updated",
  );
}
