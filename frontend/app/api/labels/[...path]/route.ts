import { NextRequest, NextResponse } from "next/server";
import { BACKEND, backendHeaders } from "../../_internal";

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(request: NextRequest, props: Ctx) {
  const params = await props.params;
  const path = params.path.join("/");
  const url = `${BACKEND}/api/labels/${path}?${request.nextUrl.searchParams}`;
  const res = await fetch(url, { headers: backendHeaders(request) });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}
