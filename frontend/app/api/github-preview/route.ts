import { NextRequest, NextResponse } from "next/server";

import { BACKEND, backendHeaders } from "../_internal";

export async function GET(request: NextRequest) {
  const repoUrl = request.nextUrl.searchParams.get("repo_url");
  if (!repoUrl) {
    return NextResponse.json({ detail: "repo_url is required" }, { status: 400 });
  }

  try {
    const backendUrl = new URL(`${BACKEND}/api/github-preview`);
    backendUrl.searchParams.set("repo_url", repoUrl);

    const res = await fetch(backendUrl.toString(), {
      headers: backendHeaders(request),
      next: { revalidate: 60 },
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { detail: "GitHub is unreachable right now. You can submit with a manual description and re-fetch later." },
      { status: 503 },
    );
  }
}
