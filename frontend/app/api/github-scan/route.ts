import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function GET(request: NextRequest) {
  const url = request.nextUrl.searchParams.get("url");
  const discover = request.nextUrl.searchParams.get("discover") ?? "false";
  if (!url) {
    return NextResponse.json({ detail: "url is required" }, { status: 400 });
  }

  const cookieStore = await cookies();
  const cookieHeader = cookieStore.toString();

  try {
    const backendUrl = new URL(`${BACKEND_URL}/api/github-scan`);
    backendUrl.searchParams.set("url", url);
    backendUrl.searchParams.set("discover", discover);

    const res = await fetch(backendUrl.toString(), {
      headers: { Cookie: cookieHeader },
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { detail: "Scan service is unreachable. Try again in a moment." },
      { status: 503 },
    );
  }
}
