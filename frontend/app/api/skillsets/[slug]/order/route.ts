import { NextRequest, NextResponse } from "next/server";

import { BACKEND, backendHeaders } from "../../../_internal";

export async function PUT(request: NextRequest, props: { params: Promise<{ slug: string }> }) {
  const params = await props.params;
  const body = await request.text();
  const res = await fetch(`${BACKEND}/api/skillsets/${encodeURIComponent(params.slug)}/order`, {
    method: "PUT",
    headers: { ...backendHeaders(request), "Content-Type": "application/json" },
    body,
  });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}
