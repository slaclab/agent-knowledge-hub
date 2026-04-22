import { NextRequest } from "next/server";

export const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";
const INTERNAL_SECRET = process.env.INTERNAL_API_SECRET ?? "";

export function backendHeaders(request: NextRequest): HeadersInit {
  return {
    "X-Forwarded-User": request.headers.get("X-Forwarded-User") ?? "",
    "X-Vouch-Idp-Claims-Name": request.headers.get("X-Vouch-Idp-Claims-Name") ?? "",
    "X-Internal-Secret": INTERNAL_SECRET,
  };
}
