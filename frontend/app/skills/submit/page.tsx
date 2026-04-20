import { AuthGuard } from "@/components/auth-guard";
import { SubmitForm } from "@/components/submit-form";
import Link from "next/link";

export default function SubmitPage() {
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
        <SubmitForm />
      </AuthGuard>
    </div>
  );
}
