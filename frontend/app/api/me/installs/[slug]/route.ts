import { NextRequest, NextResponse } from "next/server";
import { BACKEND, backendHeaders } from "../../../_internal";

export async function POST(request: NextRequest, props: { params: Promise<{ slug: string }> }) {
  const params = await props.params;
  const res = await fetch(`${BACKEND}/api/me/installs/${encodeURIComponent(params.slug)}`, {
    method: "POST",
    headers: backendHeaders(request),
  });
  if (res.status === 204) return new NextResponse(null, { status: 204 });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}
