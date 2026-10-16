import { NextRequest, NextResponse } from "next/server";

import { BACKEND, backendHeaders } from "../../../../_internal";

type Ctx = { params: Promise<{ slug: string; skill_slug: string }> };

async function forward(request: NextRequest, props: Ctx, method: "PUT" | "DELETE") {
  const params = await props.params;
  const res = await fetch(
    `${BACKEND}/api/skillsets/${encodeURIComponent(params.slug)}/skills/${encodeURIComponent(params.skill_slug)}`,
    { method, headers: backendHeaders(request) },
  );
  // NextResponse.json() throws on a 204, which would turn every successful change into a failure.
  if (res.status === 204) return new NextResponse(null, { status: 204 });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}

export async function PUT(request: NextRequest, props: Ctx) {
  return forward(request, props, "PUT");
}

export async function DELETE(request: NextRequest, props: Ctx) {
  return forward(request, props, "DELETE");
}
