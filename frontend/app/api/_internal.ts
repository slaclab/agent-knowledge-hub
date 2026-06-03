import { NextRequest } from "next/server";

export const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";
const INTERNAL_SECRET = process.env.INTERNAL_API_SECRET ?? "";

// Header name for the authenticated username. Defaults to oauth2-proxy's header;
// override with AUTH_USER_HEADER env var if your gateway uses a different name.
const AUTH_USER_HEADER = process.env.AUTH_USER_HEADER ?? "X-Auth-Request-User";
const AUTH_EMAIL_HEADER = process.env.AUTH_EMAIL_HEADER ?? "X-Auth-Request-Email";

export function backendHeaders(request: NextRequest): HeadersInit {
  // oauth2-proxy (s3df-authnz) sends X-Auth-Request-User / X-Auth-Request-Email.
  // Fall back to legacy VouchProxy headers for environments still running Vouch.
  const authRequestUser = request.headers.get(AUTH_USER_HEADER);
  const vouchName = request.headers.get("X-Vouch-Idp-Claims-Name");
  const vouchUser = request.headers.get("X-Vouch-User");
  const forwardedUser = request.headers.get("X-Forwarded-User");
  const user = authRequestUser || vouchName || vouchUser || forwardedUser || "";

  console.debug(
    "[_internal] backendHeaders: " +
      `${AUTH_USER_HEADER}=${JSON.stringify(authRequestUser)} ` +
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
