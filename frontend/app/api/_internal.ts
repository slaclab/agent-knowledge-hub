import { NextRequest } from "next/server";

export const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";
const INTERNAL_SECRET = process.env.INTERNAL_API_SECRET ?? "";

export function backendHeaders(request: NextRequest): HeadersInit {
  // Vouch injects X-Vouch-Idp-Claims-Name (SLAC username) and optionally X-Vouch-User.
  // Normalise into X-Forwarded-User so the backend Path 2 check has a reliable header.
  const vouchName = request.headers.get("X-Vouch-Idp-Claims-Name");
  const vouchUser = request.headers.get("X-Vouch-User");
  const forwardedUser = request.headers.get("X-Forwarded-User");
  const user = vouchName || vouchUser || forwardedUser || "";

  console.debug(
    "[_internal] backendHeaders: " +
      `X-Vouch-Idp-Claims-Name=${JSON.stringify(vouchName)} ` +
      `X-Vouch-User=${JSON.stringify(vouchUser)} ` +
      `X-Forwarded-User=${JSON.stringify(forwardedUser)} ` +
      `→ resolved user=${JSON.stringify(user)} ` +
      `INTERNAL_SECRET_set=${Boolean(INTERNAL_SECRET)}`,
  );

  const headers: Record<string, string> = {
    "X-Forwarded-User": user,
    "X-Internal-Secret": INTERNAL_SECRET,
  };

  // CLI tools send Authorization: Bearer <jwt> — pass it through so the backend
  // can validate it via Path 3 when X-Internal-Secret is not set (CLI has no secret).
  const auth = request.headers.get("Authorization");
  if (auth) headers["Authorization"] = auth;

  return headers;
}
