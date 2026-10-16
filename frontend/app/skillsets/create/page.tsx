import { AuthGuard } from "@/components/auth-guard";
import { SkillsetCreateForm } from "@/components/skillset-create-form";

export default function CreateSkillsetPage() {
  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Create a Skillset</h1>
        <p className="text-sm text-muted-foreground mt-1">
          A skillset is a named, ordered bundle of catalog skills that people can install together.
        </p>
      </div>

      <AuthGuard
        fallback={
          <div className="rounded-lg border border-yellow-300 bg-yellow-50 px-4 py-3 text-sm text-yellow-800">
            You must be logged in via SLAC VouchProxy to create a skillset.
          </div>
        }
      >
        <SkillsetCreateForm />
      </AuthGuard>
    </div>
  );
}
