import { notFound } from "next/navigation";
import { getSkill } from "@/lib/api";
import { EditForm } from "@/components/edit-form";
import { AuthGuard } from "@/components/auth-guard";

interface PageProps {
  params: { slug: string };
}

export default async function EditPage({ params }: PageProps) {
  const { skill, deactivated } = await getSkill(params.slug, true);

  if (!skill || deactivated) return notFound();

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Edit: {skill.name}</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Only the skill owner or an admin can save changes.
        </p>
      </div>
      <AuthGuard
        fallback={
          <div className="rounded-lg border border-yellow-300 bg-yellow-50 px-4 py-3 text-sm text-yellow-800">
            You must be logged in to edit a skill.
          </div>
        }
      >
        <EditForm skill={skill} />
      </AuthGuard>
    </div>
  );
}
