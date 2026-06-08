import { NextRequest, NextResponse } from "next/server";
import { BACKEND, backendHeaders } from "../../_internal";

export async function GET(request: NextRequest) {
  const url = `${BACKEND}/api/me/installs?${request.nextUrl.searchParams}`;
  const res = await fetch(url, { headers: backendHeaders(request) });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}
