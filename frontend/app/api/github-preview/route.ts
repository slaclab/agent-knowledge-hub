import { NextRequest, NextResponse } from "next/server";

const GITHUB_API = "https://api.github.com";
const GITHUB_TOKEN = process.env.GITHUB_TOKEN;

export async function GET(request: NextRequest) {
  const repoUrl = request.nextUrl.searchParams.get("repo_url");
  if (!repoUrl) {
    return NextResponse.json({ detail: "repo_url is required" }, { status: 400 });
  }

  const match = repoUrl.match(/^https?:\/\/github\.com\/([^/]+)\/([^/]+)\/?$/);
  if (!match) {
    return NextResponse.json({ detail: "Invalid GitHub URL" }, { status: 422 });
  }

  const [, owner, repo] = match;
  const headers: HeadersInit = { Accept: "application/vnd.github+json" };
  if (GITHUB_TOKEN) headers["Authorization"] = `Bearer ${GITHUB_TOKEN}`;

  try {
    const res = await fetch(`${GITHUB_API}/repos/${owner}/${repo}`, {
      headers,
      next: { revalidate: 60 },
    });
    if (res.status === 404) {
      return NextResponse.json(
        { detail: "This repo couldn't be found or is private. Check the URL and make sure the repo is public." },
        { status: 404 },
      );
    }
    if (!res.ok) {
      return NextResponse.json({ detail: "GitHub API error" }, { status: res.status });
    }
    const data = await res.json();
    return NextResponse.json({
      name: data.name,
      description: data.description ?? null,
      stars: data.stargazers_count ?? 0,
      license: data.license?.spdx_id ?? null,
      last_commit_at: data.pushed_at ?? null,
    });
  } catch {
    return NextResponse.json(
      { detail: "GitHub is unreachable right now. You can submit with a manual description and re-fetch later." },
      { status: 503 },
    );
  }
}
