import type { SkillStatus, VisibilityType } from "./skill";

export interface SkillsetRef {
  slug: string;
  name: string;
}

export interface SkillsetMemberOut {
  slug: string;
  name: string;
  description: string | null;
  labels: string[];
  avg_rating: number;
  visibility: VisibilityType;
  status: SkillStatus;
}

export interface SkillsetListOut {
  slug: string;
  name: string;
  description: string;
  created_by: string;
  member_count: number;
  created_at: string;
}

export interface SkillsetOut extends SkillsetListOut {
  version: number;
  skills: SkillsetMemberOut[];
}

export interface PaginatedSkillsets {
  items: SkillsetListOut[];
  total: number;
  page: number;
  page_size: number;
}

export interface SkillSummary {
  slug: string;
  name: string;
  description: string | null;
}
