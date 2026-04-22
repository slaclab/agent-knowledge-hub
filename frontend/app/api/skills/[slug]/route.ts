import { NextRequest, NextResponse } from "next/server";

import { BACKEND, backendHeaders } from "../../_internal";

export async function GET(request: NextRequest, { params }: { params: { slug: string } }) {
  const res = await fetch(`${BACKEND}/api/skills/${params.slug}`, {
    headers: backendHeaders(request),
  });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}

export async function PATCH(request: NextRequest, { params }: { params: { slug: string } }) {
  const body = await request.text();
  const res = await fetch(`${BACKEND}/api/skills/${params.slug}`, {
    method: "PATCH",
    headers: { ...backendHeaders(request), "Content-Type": "application/json" },
    body,
  });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}

export async function DELETE(request: NextRequest, { params }: { params: { slug: string } }) {
  const res = await fetch(`${BACKEND}/api/skills/${params.slug}`, {
    method: "DELETE",
    headers: backendHeaders(request),
  });
  if (res.status === 204) return new NextResponse(null, { status: 204 });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}
