export type EntryType = "skill" | "marketplace_ref";
export type SkillStatus = "active" | "deactivated";
export type VisibilityType = "public" | "internal" | "private";

export interface LabelOut {
  name: string;
  usage_count: number;
  applied_by_me: boolean;
}

export interface AdminLabelOut {
  id: string;
  name: string;
  usage_count: number;
}

export interface Skill {
  id: string;
  slug: string;
  name: string;
  repo_url: string;
  skill_path: string;
  entry_type: EntryType;
  status: SkillStatus;
  deactivation_reason: string | null;
  superseded_by_slug: string | null;
  description: string | null;
  readme_html: string | null;
  skill_md_raw: string | null;
  skill_md_filename: string | null;
  readme_raw: string | null;
  compatible_platforms: string[];
  license: string | null;
  version: string | null;
  github_stars: number | null;
  last_commit_at: string | null;
  submitter_id: string;
  submitted_at: string;
  updated_at: string;
  avg_rating: number;
  rating_count: number;
  flag_count: number;
  uses_agent_gateway: boolean;
  visibility: VisibilityType;
  forked_from_url: string | null;
  labels: LabelOut[];
  my_rating: number | null;
}

export interface RateSkillOut {
  avg_rating: number;
  rating_count: number;
  my_rating: number;
}

export interface PaginatedSkills {
  items: Skill[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface SkillRevision {
  id: string;
  skill_id: string;
  revision_number: number;
  snapshot: Record<string, unknown>;
  actor_id: string;
  action: "create" | "edit" | "refetch" | "deactivate" | "reactivate";
  changelog_note: string | null;
  created_at: string;
}

export interface SkillCreate {
  repo_url: string;
  skill_path?: string;
  name?: string;
  description?: string;
  compatible_platforms?: string[];
  keywords?: string[];  // deprecated: converted to labels on create
  version?: string;
  license?: string;
}

export interface SkillUpdate {
  name?: string;
  description?: string;
  compatible_platforms?: string[];
  version?: string;
  license?: string;
  changelog_note?: string;
  forked_from_url?: string;
}

export interface User {
  user_id: string;
  is_admin: boolean;
}

export interface GitHubPreview {
  name: string;
  description: string | null;
  stars: number;
  license: string | null;
  last_commit_at: string | null;
  visibility: VisibilityType;
}

export type SortOption = "newest" | "highest_rated" | "most_rated" | "most_stars";

export interface SkillListParams {
  q?: string;
  labels?: string[];
  sort?: SortOption;
  page?: number;
  page_size?: number;
  forked_from?: string;
  visibility?: VisibilityType | "all";
}

export interface GitHubRef {
  owner: string;
  repo: string;
  branch: string | null;
  path: string;
}

export interface SkillScanSnapshot {
  ref: GitHubRef;
  name: string | null;
  description: string | null;
  compatible_platforms: string[];
  version: string | null;
  license: string | null;
  readme_html: string | null;
  stars: number;
  last_commit_at: string | null;
  visibility: VisibilityType;
  forked_from_url: string | null;
  fetched_at: string;
  no_skill_files: boolean;
  existing_slug: string | null;
}

export interface DiscoverResult {
  skills: SkillScanSnapshot[];
  tree_truncated: boolean;
  capped: boolean;
}
