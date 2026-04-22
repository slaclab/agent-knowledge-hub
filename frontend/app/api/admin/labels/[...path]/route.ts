import { NextRequest, NextResponse } from "next/server";
import { BACKEND, backendHeaders } from "../../../_internal";

type Ctx = { params: { path: string[] } };

async function proxyJson(request: NextRequest, method: string, backendUrl: string) {
  const body = method !== "GET" && method !== "DELETE" ? await request.text() : undefined;
  const res = await fetch(backendUrl, {
    method,
    headers: { ...backendHeaders(request), "Content-Type": "application/json" },
    body,
  });
  if (res.status === 204) return new NextResponse(null, { status: 204 });
  const data = await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}

export async function GET(request: NextRequest, { params }: Ctx) {
  const url = `${BACKEND}/api/admin/labels/${params.path.join("/")}?${request.nextUrl.searchParams}`;
  return proxyJson(request, "GET", url);
}

export async function PATCH(request: NextRequest, { params }: Ctx) {
  return proxyJson(request, "PATCH", `${BACKEND}/api/admin/labels/${params.path.join("/")}`);
}

export async function POST(request: NextRequest, { params }: Ctx) {
  return proxyJson(request, "POST", `${BACKEND}/api/admin/labels/${params.path.join("/")}`);
}

export async function DELETE(request: NextRequest, { params }: Ctx) {
  return proxyJson(request, "DELETE", `${BACKEND}/api/admin/labels/${params.path.join("/")}`);
}
