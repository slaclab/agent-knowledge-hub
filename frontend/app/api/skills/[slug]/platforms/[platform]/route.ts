import { NextRequest, NextResponse } from "next/server";
import { BACKEND, backendHeaders } from "../../../../_internal";

type Ctx = { params: Promise<{ slug: string; platform: string }> };

export async function DELETE(request: NextRequest, props: Ctx) {
  const params = await props.params;
  const res = await fetch(`${BACKEND}/api/skills/${params.slug}/platforms/${encodeURIComponent(params.platform)}`, {
    method: "DELETE",
    headers: backendHeaders(request),
  });
  if (res.status === 204) return new NextResponse(null, { status: 204 });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}
