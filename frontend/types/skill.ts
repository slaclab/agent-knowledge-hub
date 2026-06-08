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
  agent_count: number;
  agent_names: string[];
  has_mcp_server: boolean;
  has_scripts: boolean;
  plugin_author: string | null;
  file_manifest: FileManifestEntry[];
  manifest_truncated: boolean;
  // version pinning (#017)
  pinned_commit_sha: string | null;
  pinned_ref: string | null;
  upstream_sha: string | null;
  update_available: boolean;
  labels: LabelOut[];
  my_rating: number | null;
  my_flag: FlagOut | null;
}

export type FlagReason = "broken" | "stale" | "superseded" | "inappropriate" | "other";
export type FlagStatus = "active" | "resolved";

export interface FlagOut {
  reason: FlagReason;
  note: string | null;
  status: FlagStatus;
  created_at: string;
}

export interface FlagResponse {
  flag_count: number;
  my_flag: FlagOut | null;
}

export interface RetractResponse {
  flag_count: number;
}

export interface FlaggedSkillItem {
  skill_slug: string;
  skill_name: string;
  flag_count: number;
  flags: Array<{
    reason: FlagReason;
    note: string | null;
    status: FlagStatus;
    created_at: string;
    reporter_id: string;
  }>;
}

export interface PaginatedFlaggedSkills {
  items: FlaggedSkillItem[];
  total: number;
  page: number;
  pages: number;
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
  next_cursor: string | null;
  prev_cursor: string | null;
  platform_counts?: Record<string, number>;
}

export interface SkillRevision {
  id: string;
  skill_id: string;
  revision_number: number;
  snapshot: Record<string, unknown>;
  actor_id: string;
  action: "create" | "edit" | "refetch" | "deactivate" | "reactivate" | "pin";
  changelog_note: string | null;
  created_at: string;
}

export type FieldDiff =
  | { field: string; type: "scalar"; old: string | number | null; new: string | number | null }
  | { field: string; type: "array"; added: string[]; removed: string[] }
  | { field: string; type: "readme_updated" };

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

export interface UserProfile {
  user_id: string;
  submitted_count: number;
  edited_count: number;
  install_count?: number; // only present for self or admin viewer
}

export interface InstallEvent {
  skill_slug: string;
  skill_name: string | null;
  installed_at: string;
  update_available: boolean;
  is_deleted: boolean;
}

export interface PaginatedInstalls {
  items: InstallEvent[];
  total: number;
  page: number;
  page_size: number;
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
  cursor?: string;
  platforms?: string[];
}

export interface GitHubRef {
  owner: string;
  repo: string;
  branch: string | null;
  path: string;
}

export interface FileManifestEntry {
  path: string;
  size_bytes: number;
  is_text: boolean;
  is_dir: boolean;
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
  agent_count: number;
  agent_names: string[];
  has_mcp_server: boolean;
  has_scripts: boolean;
  plugin_author: string | null;
  keywords: string[];
  file_manifest: FileManifestEntry[];
  manifest_truncated: boolean;
}

export interface DiscoverResult {
  skills: SkillScanSnapshot[];
  tree_truncated: boolean;
  capped: boolean;
}
