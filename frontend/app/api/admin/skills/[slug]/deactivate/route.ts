import { NextRequest, NextResponse } from "next/server";
import { BACKEND, backendHeaders } from "../../../../_internal";

type Ctx = { params: { slug: string } };

export async function POST(request: NextRequest, { params }: Ctx) {
  const body = await request.text();
  const res = await fetch(`${BACKEND}/api/admin/skills/${params.slug}/deactivate`, {
    method: "POST",
    headers: { ...backendHeaders(request), "Content-Type": "application/json" },
    body,
  });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}
