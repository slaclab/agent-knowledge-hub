import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function GET(request: NextRequest) {
  const repoUrl = request.nextUrl.searchParams.get("repo_url");
  if (!repoUrl) {
    return NextResponse.json({ detail: "repo_url is required" }, { status: 400 });
  }

  try {
    const backendUrl = new URL(`${BACKEND_URL}/api/github-preview`);
    backendUrl.searchParams.set("repo_url", repoUrl);

    const res = await fetch(backendUrl.toString(), { next: { revalidate: 60 } });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { detail: "GitHub is unreachable right now. You can submit with a manual description and re-fetch later." },
      { status: 503 },
    );
  }
}
