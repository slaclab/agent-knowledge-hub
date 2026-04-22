import { NextRequest, NextResponse } from "next/server";

import { BACKEND, backendHeaders } from "../_internal";

export async function GET(request: NextRequest) {
  const url = request.nextUrl.searchParams.get("url");
  const discover = request.nextUrl.searchParams.get("discover") ?? "false";
  if (!url) {
    return NextResponse.json({ detail: "url is required" }, { status: 400 });
  }

  try {
    const backendUrl = new URL(`${BACKEND}/api/github-scan`);
    backendUrl.searchParams.set("url", url);
    backendUrl.searchParams.set("discover", discover);

    const res = await fetch(backendUrl.toString(), { headers: backendHeaders(request) });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { detail: "Scan service is unreachable. Try again in a moment." },
      { status: 503 },
    );
  }
}
