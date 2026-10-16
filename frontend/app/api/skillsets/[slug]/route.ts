import { NextRequest, NextResponse } from "next/server";

import { BACKEND, backendHeaders } from "../../_internal";

type Ctx = { params: Promise<{ slug: string }> };

// Next.js decodes path parameters, so each one is encoded again to stay one path segment.
function backendUrl(slug: string) {
  return `${BACKEND}/api/skillsets/${encodeURIComponent(slug)}`;
}

export async function GET(request: NextRequest, props: Ctx) {
  const params = await props.params;
  const res = await fetch(backendUrl(params.slug), { headers: backendHeaders(request) });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}

export async function PATCH(request: NextRequest, props: Ctx) {
  const params = await props.params;
  const body = await request.text();
  const res = await fetch(backendUrl(params.slug), {
    method: "PATCH",
    headers: { ...backendHeaders(request), "Content-Type": "application/json" },
    body,
  });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}

export async function DELETE(request: NextRequest, props: Ctx) {
  const params = await props.params;
  const res = await fetch(backendUrl(params.slug), {
    method: "DELETE",
    headers: backendHeaders(request),
  });
  if (res.status === 204) return new NextResponse(null, { status: 204 });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}
