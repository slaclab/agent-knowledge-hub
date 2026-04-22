import { NextRequest, NextResponse } from "next/server";

import { BACKEND, backendHeaders } from "../_internal";

export async function GET(request: NextRequest) {
  const url = `${BACKEND}/api/skills?${request.nextUrl.searchParams}`;
  const res = await fetch(url, { headers: backendHeaders(request) });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}

export async function POST(request: NextRequest) {
  const body = await request.text();
  const res = await fetch(`${BACKEND}/api/skills`, {
    method: "POST",
    headers: { ...backendHeaders(request), "Content-Type": "application/json" },
    body,
  });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}
