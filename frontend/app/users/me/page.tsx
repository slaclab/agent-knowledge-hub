import { headers } from "next/headers";
import { redirect } from "next/navigation";

export default function MeRedirectPage() {
  const h = headers();
  const viewer =
    h.get(process.env.AUTH_USER_HEADER ?? "x-auth-request-user") ||
    h.get("x-vouch-idp-claims-name") ||
    h.get("x-vouch-user") ||
    h.get("x-forwarded-user") ||
    null;

  if (!viewer) {
    // Unauthenticated — send to skill list; they'll see the sign-in prompt there
    redirect("/skills");
  }

  redirect(`/users/${encodeURIComponent(viewer)}`);
}
