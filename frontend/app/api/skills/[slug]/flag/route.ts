import { NextRequest, NextResponse } from "next/server";
import { BACKEND, backendHeaders } from "../../../_internal";

type Ctx = { params: { slug: string } };

export async function POST(request: NextRequest, { params }: Ctx) {
  const body = await request.text();
  const res = await fetch(`${BACKEND}/api/skills/${params.slug}/flag`, {
    method: "POST",
    headers: { ...backendHeaders(request), "Content-Type": "application/json" },
    body,
  });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}

export async function DELETE(request: NextRequest, { params }: Ctx) {
  const res = await fetch(`${BACKEND}/api/skills/${params.slug}/flag`, {
    method: "DELETE",
    headers: backendHeaders(request),
  });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}
