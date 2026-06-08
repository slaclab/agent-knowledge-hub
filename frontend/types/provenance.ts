export interface ProvenanceNode {
  slug: string | null;
  name: string;
  repo_url: string;
  in_catalog: boolean;
  visibility: string | null;
  submitter_id: string | null;
  github_stars: number | null;
  avg_rating: number | null;
  last_commit_at: string | null;
  status: string | null;
  forks: ProvenanceNode[];
  forks_truncated: boolean;
  total_fork_count: number;
}

export interface ProvenanceTree {
  empty: boolean;
  subject: ProvenanceNode | null;
  upstream: ProvenanceNode[];
  supersession: ProvenanceNode[];
}
