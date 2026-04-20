import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest, { params }: { params: { slug: string } }) {
  const res = await fetch(`${BACKEND}/api/skills/${params.slug}/refetch`, {
    method: "POST",
    headers: { "X-Forwarded-User": request.headers.get("X-Forwarded-User") ?? "" },
  });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}
