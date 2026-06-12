import { NextRequest, NextResponse } from "next/server";

import { BACKEND, backendHeaders } from "../_internal";

export async function GET(request: NextRequest) {
  // DEBUG: log all headers received from nginx (includes Vouch-injected headers)
  const allHeaders: Record<string, string> = {};
  request.headers.forEach((v, k) => {
    allHeaders[k] =
      k.toLowerCase() === "x-internal-secret" ? "[REDACTED]" : v;
  });
  console.debug("[me/route] incoming headers from nginx:", JSON.stringify(allHeaders));

  const outHeaders = backendHeaders(request);
  if (process.env.NODE_ENV !== "production") {
    const safeOut = { ...(outHeaders as Record<string, string>), "X-Internal-Secret": "[REDACTED]" };
    console.debug("[me/route] outgoing headers to backend:", JSON.stringify(safeOut));
  }

  const res = await fetch(`${BACKEND}/api/me`, { headers: outHeaders });
  const data = await res.json().catch(() => null);
  console.debug("[me/route] backend response status=%d body=%s", res.status, JSON.stringify(data));
  return NextResponse.json(data, { status: res.status });
}
