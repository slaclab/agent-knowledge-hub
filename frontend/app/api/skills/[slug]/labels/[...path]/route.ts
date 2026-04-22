import { NextRequest, NextResponse } from "next/server";
import { BACKEND, backendHeaders } from "../../../../_internal";

type Ctx = { params: { slug: string; path: string[] } };

export async function GET(request: NextRequest, { params }: Ctx) {
  const res = await fetch(`${BACKEND}/api/skills/${params.slug}/labels/${params.path.join("/")}`, {
    headers: backendHeaders(request),
  });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}

export async function DELETE(request: NextRequest, { params }: Ctx) {
  const res = await fetch(`${BACKEND}/api/skills/${params.slug}/labels/${params.path.join("/")}`, {
    method: "DELETE",
    headers: backendHeaders(request),
  });
  if (res.status === 204) return new NextResponse(null, { status: 204 });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}
