import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function GET(request: NextRequest) {
  const res = await fetch(`${BACKEND}/api/me`, {
    headers: { "X-Forwarded-User": request.headers.get("X-Forwarded-User") ?? "" },
  });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}
