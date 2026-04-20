import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

function forwardHeaders(request: NextRequest): HeadersInit {
  return { "X-Forwarded-User": request.headers.get("X-Forwarded-User") ?? "" };
}

export async function GET(request: NextRequest, { params }: { params: { slug: string } }) {
  const res = await fetch(`${BACKEND}/api/skills/${params.slug}`, {
    headers: forwardHeaders(request),
  });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}

export async function PATCH(request: NextRequest, { params }: { params: { slug: string } }) {
  const body = await request.text();
  const res = await fetch(`${BACKEND}/api/skills/${params.slug}`, {
    method: "PATCH",
    headers: { ...forwardHeaders(request), "Content-Type": "application/json" },
    body,
  });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}

export async function DELETE(request: NextRequest, { params }: { params: { slug: string } }) {
  const res = await fetch(`${BACKEND}/api/skills/${params.slug}`, {
    method: "DELETE",
    headers: forwardHeaders(request),
  });
  if (res.status === 204) return new NextResponse(null, { status: 204 });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}
