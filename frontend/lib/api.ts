import type {
  Skill,
  PaginatedSkills,
  SkillCreate,
  SkillUpdate,
  SkillRevision,
  User,
  UserProfile,
  PaginatedInstalls,
  GitHubPreview,
  SkillListParams,
  SkillScanSnapshot,
  DiscoverResult,
  LabelOut,
  RateSkillOut,
  FlagResponse,
  RetractResponse,
  PaginatedFlaggedSkills,
} from "@/types/skill";
import type { ProvenanceTree } from "@/types/provenance";

// Server Components call with server=true to hit FastAPI directly (BACKEND_URL).
// Client Components use server=false (default) to call Next.js proxy route handlers.
const CLIENT_BASE = "/api";
const SERVER_BASE = `${process.env.BACKEND_URL ?? "http://localhost:8000"}/api`;

function apiBase(server = false) {
  return server ? SERVER_BASE : CLIENT_BASE;
}

async function request<T>(
  b: string,
  path: string,
  init?: RequestInit,
): Promise<{ data: T | null; error: string | null; status: number }> {
  const res = await fetch(`${b}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
    ...init,
  });
  if (res.status === 204) return { data: null, error: null, status: 204 };
  const json = await res.json().catch(() => null);
  if (!res.ok) {
    const error = (json?.detail as string | undefined) ?? `HTTP ${res.status}`;
    return { data: null, error, status: res.status };
  }
  return { data: json as T, error: null, status: res.status };
}

export async function getMe(server = false): Promise<User | null> {
  const { data } = await request<User>(apiBase(server), "/me");
  return data;
}

export async function listSkills(
  params: SkillListParams & { server?: boolean } = {},
): Promise<PaginatedSkills | null> {
  const { server, ...rest } = params;
  const qs = new URLSearchParams();
  if (rest.q) qs.set("q", rest.q);
  if (rest.labels?.length) qs.set("labels", rest.labels.join(","));
  if (rest.sort) qs.set("sort", rest.sort);
  if (rest.page) qs.set("page", String(rest.page));
  if (rest.page_size) qs.set("page_size", String(rest.page_size));
  if (rest.forked_from) qs.set("forked_from", rest.forked_from);
  if (rest.visibility) qs.set("visibility", rest.visibility);
  if (rest.cursor) qs.set("cursor", rest.cursor);
  if (rest.platforms?.length) qs.set("platforms", rest.platforms.join(","));
  const { data } = await request<PaginatedSkills>(apiBase(server), `/skills?${qs}`);
  return data;
}

export async function getSkill(
  slug: string,
  server = false,
  viewerName?: string,
): Promise<{ skill: Skill | null; deactivated: boolean; reason: string | null; superseded_by_slug?: string | null }> {
  const b = apiBase(server);
  const fetchHeaders: HeadersInit = {};
  if (server && viewerName) {
    fetchHeaders["X-Forwarded-User"] = viewerName;
    const secret = process.env.INTERNAL_API_SECRET;
    if (secret) fetchHeaders["X-Internal-Secret"] = secret;
  }
  const res = await fetch(`${b}/skills/${slug}`, { cache: "no-store", headers: fetchHeaders });
  if (res.status === 410) {
    const json = await res.json().catch(() => ({}));
    const detail = (json as { detail?: { code?: string; reason?: string; superseded_by_slug?: string } | string }).detail;
    const reason = typeof detail === "object" ? (detail?.reason ?? null) : (detail ?? null);
    const superseded_by_slug = typeof detail === "object" ? (detail?.superseded_by_slug ?? null) : null;
    return { skill: null, deactivated: true, reason, superseded_by_slug };
  }
  if (!res.ok) return { skill: null, deactivated: false, reason: null };
  const skill = (await res.json()) as Skill;
  return { skill, deactivated: false, reason: null };
}

export async function createSkill(
  data: SkillCreate,
): Promise<{ data: Skill | null; error: string | null }> {
  const r = await request<Skill>(CLIENT_BASE, "/skills", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return { data: r.data, error: r.error };
}

export async function updateSkill(
  slug: string,
  data: SkillUpdate,
): Promise<{ data: Skill | null; error: string | null }> {
  const r = await request<Skill>(CLIENT_BASE, `/skills/${slug}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
  return { data: r.data, error: r.error };
}

export async function deleteSkill(slug: string): Promise<{ error: string | null }> {
  const r = await request<null>(CLIENT_BASE, `/skills/${slug}`, { method: "DELETE" });
  return { error: r.error };
}

export async function refetchSkill(
  slug: string,
): Promise<{ data: Skill | null; error: string | null }> {
  const r = await request<Skill>(CLIENT_BASE, `/skills/${slug}/refetch`, { method: "POST" });
  return { data: r.data, error: r.error };
}

export async function pinSkill(
  slug: string,
): Promise<{ data: Skill | null; error: string | null }> {
  const r = await request<Skill>(CLIENT_BASE, `/skills/${slug}/pin`, { method: "POST" });
  return { data: r.data, error: r.error };
}

export async function getRevisions(slug: string, server = false): Promise<SkillRevision[]> {
  const { data } = await request<SkillRevision[]>(apiBase(server), `/skills/${slug}/revisions`);
  return data ?? [];
}

export async function getProvenance(slug: string, server = false): Promise<ProvenanceTree | null> {
  const { data } = await request<ProvenanceTree>(apiBase(server), `/skills/${slug}/provenance`);
  return data;
}

export async function getSettings(server = false): Promise<{ github_access_instructions_url: string }> {
  const fallback = { github_access_instructions_url: "/guides/slac-github-access" };
  try {
    const { data } = await request<{ github_access_instructions_url: string }>(
      apiBase(server),
      "/settings",
    );
    return data ?? fallback;
  } catch {
    return fallback;
  }
}

export async function getGithubPreview(
  repoUrl: string,
): Promise<{ data: GitHubPreview | null; error: string | null }> {
  const qs = new URLSearchParams({ repo_url: repoUrl });
  const r = await request<GitHubPreview>(CLIENT_BASE, `/github-preview?${qs}`);
  return { data: r.data, error: r.error };
}

export async function getGithubScan(
  url: string,
  discover = false,
): Promise<{ data: SkillScanSnapshot | null; error: string | null; status: number }> {
  const qs = new URLSearchParams({ url, discover: String(discover) });
  const r = await request<SkillScanSnapshot>(CLIENT_BASE, `/github-scan?${qs}`);
  return { data: r.data, error: r.error, status: r.status };
}

export async function getGithubDiscover(
  url: string,
): Promise<{ data: DiscoverResult | null; error: string | null }> {
  const qs = new URLSearchParams({ url, discover: "true" });
  const r = await request<DiscoverResult>(CLIENT_BASE, `/github-scan?${qs}`);
  return { data: r.data, error: r.error };
}

export async function listLabels(params: { q?: string; limit?: number; server?: boolean } = {}): Promise<LabelOut[]> {
  const { server, ...rest } = params;
  const qs = new URLSearchParams();
  if (rest.q) qs.set("q", rest.q);
  if (rest.limit) qs.set("limit", String(rest.limit));
  const { data } = await request<LabelOut[]>(apiBase(server), `/labels?${qs}`);
  return data ?? [];
}

export async function addLabel(
  slug: string,
  name: string,
): Promise<{ data: LabelOut | null; error: string | null; status: number }> {
  const r = await request<LabelOut>(CLIENT_BASE, `/skills/${slug}/labels`, {
    method: "POST",
    body: JSON.stringify({ name }),
  });
  return { data: r.data, error: r.error, status: r.status };
}

export async function removeLabel(
  slug: string,
  name: string,
): Promise<{ error: string | null }> {
  const r = await request<null>(CLIENT_BASE, `/skills/${slug}/labels/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
  return { error: r.error };
}

export async function addPlatform(
  slug: string,
  platform: string,
): Promise<{ data: Skill | null; error: string | null; status: number }> {
  const r = await request<Skill>(CLIENT_BASE, `/skills/${slug}/platforms`, {
    method: "POST",
    body: JSON.stringify({ platform }),
  });
  return { data: r.data, error: r.error, status: r.status };
}

export async function removePlatform(
  slug: string,
  platform: string,
): Promise<{ error: string | null }> {
  const r = await request<null>(CLIENT_BASE, `/skills/${slug}/platforms/${encodeURIComponent(platform)}`, {
    method: "DELETE",
  });
  return { error: r.error };
}

export async function listSkillLabels(slug: string): Promise<LabelOut[]> {
  const { data } = await request<LabelOut[]>(CLIENT_BASE, `/skills/${slug}/labels`);
  return data ?? [];
}

export async function rateSkill(
  slug: string,
  value: number,
): Promise<{ data: RateSkillOut | null; error: string | null }> {
  const r = await request<RateSkillOut>(CLIENT_BASE, `/skills/${slug}/rate`, {
    method: "POST",
    body: JSON.stringify({ value }),
  });
  return { data: r.data, error: r.error };
}

export async function getUserProfile(userId: string): Promise<UserProfile | null> {
  const { data } = await request<UserProfile>(CLIENT_BASE, `/users/${encodeURIComponent(userId)}`);
  return data;
}

export async function getUserSkills(
  userId: string,
  page = 1,
  pageSize = 20,
): Promise<PaginatedSkills | null> {
  const { data } = await request<PaginatedSkills>(
    CLIENT_BASE,
    `/users/${encodeURIComponent(userId)}/skills?page=${page}&page_size=${pageSize}`,
  );
  return data;
}

export async function getUserEdits(
  userId: string,
  page = 1,
  pageSize = 20,
): Promise<PaginatedSkills | null> {
  const { data } = await request<PaginatedSkills>(
    CLIENT_BASE,
    `/users/${encodeURIComponent(userId)}/edits?page=${page}&page_size=${pageSize}`,
  );
  return data;
}

export async function getMyInstalls(page = 1, pageSize = 20): Promise<PaginatedInstalls | null> {
  const { data } = await request<PaginatedInstalls>(
    CLIENT_BASE,
    `/me/installs?page=${page}&page_size=${pageSize}`,
  );
  return data;
}

export async function getUserInstalls(
  userId: string,
  page = 1,
  pageSize = 20,
): Promise<PaginatedInstalls | null> {
  const { data } = await request<PaginatedInstalls>(
    CLIENT_BASE,
    `/users/${encodeURIComponent(userId)}/installs?page=${page}&page_size=${pageSize}`,
  );
  return data;
}

export async function recordInstall(slug: string): Promise<void> {
  await request(CLIENT_BASE, `/me/installs/${encodeURIComponent(slug)}`, { method: "POST" });
}

export async function flagSkill(
  slug: string,
  reason: string,
  note?: string,
  superseded_by_slug?: string,
): Promise<FlagResponse | null> {
  const { data } = await request<FlagResponse>(CLIENT_BASE, `/skills/${encodeURIComponent(slug)}/flag`, {
    method: "POST",
    body: JSON.stringify({ reason, note: note ?? null, superseded_by_slug: superseded_by_slug ?? null }),
  });
  return data;
}

export async function retractFlag(slug: string): Promise<RetractResponse | null> {
  const { data } = await request<RetractResponse>(CLIENT_BASE, `/skills/${encodeURIComponent(slug)}/flag`, {
    method: "DELETE",
  });
  return data;
}

export async function getAdminFlags(page = 1, pageSize = 20): Promise<PaginatedFlaggedSkills | null> {
  const { data } = await request<PaginatedFlaggedSkills>(
    CLIENT_BASE,
    `/admin/flags?page=${page}&page_size=${pageSize}`,
  );
  return data;
}

export async function deactivateSkill(
  slug: string,
  reason: string,
  superseded_by_slug?: string,
): Promise<{ slug: string; status: string; warnings: string[] } | null> {
  const { data } = await request<{ slug: string; status: string; warnings: string[] }>(
    CLIENT_BASE,
    `/admin/skills/${encodeURIComponent(slug)}/deactivate`,
    {
      method: "POST",
      body: JSON.stringify({ reason, superseded_by_slug: superseded_by_slug ?? null }),
    },
  );
  return data;
}

export async function reactivateSkill(
  slug: string,
  reason?: string,
): Promise<{ slug: string; status: string } | null> {
  const { data } = await request<{ slug: string; status: string }>(
    CLIENT_BASE,
    `/admin/skills/${encodeURIComponent(slug)}/reactivate`,
    { method: "POST", body: JSON.stringify({ reason: reason ?? null }) },
  );
  return data;
}
