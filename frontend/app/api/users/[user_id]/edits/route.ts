import { NextRequest, NextResponse } from "next/server";
import { BACKEND, backendHeaders } from "../../../_internal";

export async function GET(request: NextRequest, { params }: { params: { user_id: string } }) {
  const url = `${BACKEND}/api/users/${encodeURIComponent(params.user_id)}/edits?${request.nextUrl.searchParams}`;
  const res = await fetch(url, { headers: backendHeaders(request) });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}
