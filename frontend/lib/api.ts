import type {
  Skill,
  PaginatedSkills,
  SkillCreate,
  SkillUpdate,
  SkillRevision,
  User,
  GitHubPreview,
  SkillListParams,
} from "@/types/skill";

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
  const { data } = await request<PaginatedSkills>(apiBase(server), `/skills?${qs}`);
  return data;
}

export async function getSkill(
  slug: string,
  server = false,
): Promise<{ skill: Skill | null; deactivated: boolean; reason: string | null }> {
  const b = apiBase(server);
  const res = await fetch(`${b}/skills/${slug}`);
  if (res.status === 410) {
    const json = await res.json().catch(() => ({}));
    return { skill: null, deactivated: true, reason: (json as { detail?: string }).detail ?? null };
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

export async function getRevisions(slug: string, server = false): Promise<SkillRevision[]> {
  const { data } = await request<SkillRevision[]>(apiBase(server), `/skills/${slug}/revisions`);
  return data ?? [];
}

export async function getGithubPreview(
  repoUrl: string,
): Promise<{ data: GitHubPreview | null; error: string | null }> {
  const qs = new URLSearchParams({ repo_url: repoUrl });
  const r = await request<GitHubPreview>(CLIENT_BASE, `/github-preview?${qs}`);
  return { data: r.data, error: r.error };
}
