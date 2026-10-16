import { NextRequest, NextResponse } from "next/server";
import { BACKEND, backendHeaders } from "../../../_internal";

type Ctx = { params: Promise<{ path: string[] }> };

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

function encodedPath(parts: string[]): string {
  return parts.map(encodeURIComponent).join("/");
}

export async function GET(request: NextRequest, props: Ctx) {
  const params = await props.params;
  const url = `${BACKEND}/api/admin/labels/${encodedPath(params.path)}?${request.nextUrl.searchParams}`;
  return proxyJson(request, "GET", url);
}

export async function PATCH(request: NextRequest, props: Ctx) {
  const params = await props.params;
  return proxyJson(request, "PATCH", `${BACKEND}/api/admin/labels/${encodedPath(params.path)}`);
}

export async function POST(request: NextRequest, props: Ctx) {
  const params = await props.params;
  return proxyJson(request, "POST", `${BACKEND}/api/admin/labels/${encodedPath(params.path)}`);
}

export async function DELETE(request: NextRequest, props: Ctx) {
  const params = await props.params;
  return proxyJson(request, "DELETE", `${BACKEND}/api/admin/labels/${encodedPath(params.path)}`);
}
