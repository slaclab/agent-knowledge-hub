import { AuthGuard } from "@/components/auth-guard";
import { SubmitForm } from "@/components/submit-form";
import { getSettings, getSkillset } from "@/lib/api";
import Link from "next/link";

export const dynamic = "force-dynamic";

interface PageProps {
  searchParams: Promise<{ skillset?: string | string[] }>;
}

export default async function SubmitPage(props: PageProps) {
  const searchParams = await props.searchParams;
  // ?skillset=<slug> from a skillset page's "Add new skill →" (FR-2a). The form decides whether
  // the viewer owns it; the backend checks again and ignores the slug otherwise (FR-2b).
  const skillsetSlug = typeof searchParams.skillset === "string" ? searchParams.skillset : null;
  const [siteSettings, skillset] = await Promise.all([
    getSettings(true),
    skillsetSlug ? getSkillset(skillsetSlug, true).catch(() => null) : null,
  ]);

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Submit a Skill</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Add a GitHub-hosted agent skill or plugin to the catalog.{" "}
          <Link href="/guides" className="text-primary underline">
            Need help creating a skill?
          </Link>
        </p>
      </div>

      <AuthGuard
        fallback={
          <div className="rounded-lg border border-yellow-300 bg-yellow-50 px-4 py-3 text-sm text-yellow-800">
            You must be logged in via SLAC VouchProxy to submit a skill.
          </div>
        }
      >
        <SubmitForm
          accessInstructionsUrl={siteSettings.github_access_instructions_url}
          skillset={skillset ? { slug: skillset.slug, name: skillset.name, created_by: skillset.created_by } : null}
        />
      </AuthGuard>
    </div>
  );
}
