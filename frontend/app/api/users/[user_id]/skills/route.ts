import { NextRequest, NextResponse } from "next/server";
import { BACKEND, backendHeaders } from "../../../_internal";

export async function GET(request: NextRequest, props: { params: Promise<{ user_id: string }> }) {
  const params = await props.params;
  const url = `${BACKEND}/api/users/${encodeURIComponent(params.user_id)}/skills?${request.nextUrl.searchParams}`;
  const res = await fetch(url, { headers: backendHeaders(request) });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}
