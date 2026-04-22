import { NextRequest, NextResponse } from "next/server";

import { BACKEND, backendHeaders } from "../../../../_internal";

export async function GET(
  request: NextRequest,
  { params }: { params: { slug: string; n: string } },
) {
  const res = await fetch(`${BACKEND}/api/skills/${params.slug}/revisions/${params.n}`, {
    headers: backendHeaders(request),
  });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}
