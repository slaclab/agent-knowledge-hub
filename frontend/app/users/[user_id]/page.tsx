import { headers } from "next/headers";
import { notFound } from "next/navigation";
import { getUserProfile } from "@/lib/api";
import { UserActivityTabs } from "@/components/user-activity-tabs";

interface PageProps {
  params: { user_id: string };
}

export default async function UserProfilePage({ params }: PageProps) {
  const { user_id } = params;
  const h = headers();
  const viewer =
    h.get(process.env.AUTH_USER_HEADER ?? "x-auth-request-user") ||
    h.get("x-vouch-idp-claims-name") ||
    h.get("x-vouch-user") ||
    h.get("x-forwarded-user") ||
    null;

  const profile = await getUserProfile(user_id);
  // getUserProfile returns zeros for unknown users — it only fails on network error
  if (!profile) return notFound();

  const isOwnProfile = viewer === user_id;
  // is_admin not available in SSR without a backend call; canViewInstalls is determined
  // client-side in UserActivityTabs based on profile ownership
  const canViewInstalls = isOwnProfile;

  return (
    <div className="max-w-3xl mx-auto py-8 px-4 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">{user_id}</h1>
        <div className="flex gap-4 mt-2 text-sm text-muted-foreground">
          <span>{profile.submitted_count} submitted</span>
          <span>{profile.edited_count} edited</span>
          {profile.install_count !== undefined && (
            <span>{profile.install_count} installed</span>
          )}
        </div>
      </div>

      <UserActivityTabs
        userId={user_id}
        canViewInstalls={canViewInstalls}
        isOwnProfile={isOwnProfile}
      />
    </div>
  );
}
