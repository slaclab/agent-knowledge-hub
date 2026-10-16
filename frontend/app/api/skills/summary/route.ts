import { NextRequest, NextResponse } from "next/server";

import { BACKEND, backendHeaders } from "../../_internal";

// Without this handler, skills/[slug] would serve the request as slug "summary" and drop ?q=.
export async function GET(request: NextRequest) {
  const url = `${BACKEND}/api/skills/summary?${request.nextUrl.searchParams}`;
  const res = await fetch(url, { headers: backendHeaders(request) });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}
