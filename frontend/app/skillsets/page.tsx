import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { listSkillsets } from "@/lib/api";
import { AuthGuard } from "@/components/auth-guard";
import { SkillsetCard } from "@/components/skillset-card";

const PAGE_SIZE = 20;

interface PageProps {
  searchParams: Promise<{ page?: string }>;
}

export default async function SkillsetsPage(props: PageProps) {
  const searchParams = await props.searchParams;
  const page = Math.max(1, Math.floor(Number(searchParams.page)) || 1);
  const data = await listSkillsets({ page, page_size: PAGE_SIZE, server: true });

  if (!data) {
    return (
      <div className="text-center py-16 text-muted-foreground">
        <p>Failed to load skillsets. The backend may be unavailable.</p>
      </div>
    );
  }

  const pages = Math.ceil(data.total / PAGE_SIZE);
  const pageLink = "inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-sm hover:bg-muted transition-colors";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Skillsets</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Curated bundles of skills. Install a whole set with{" "}
            <code className="font-mono text-xs">/agent-knowledge-hub install skillset &lt;slug&gt;</code>.
          </p>
        </div>
        <AuthGuard>
          <Link
            href="/skillsets/create"
            className="inline-flex items-center rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors shrink-0"
          >
            + Create Skillset
          </Link>
        </AuthGuard>
      </div>

      {data.total === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <AuthGuard
            fallback={<p>No skillsets yet. Skillsets are curated bundles of skills. Sign in to create one.</p>}
          >
            <p>
              No skillsets yet.{" "}
              <Link href="/skillsets/create" className="text-primary underline">
                Create a skillset →
              </Link>
            </p>
          </AuthGuard>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {data.items.map((s) => (
            <SkillsetCard key={s.slug} skillset={s} />
          ))}
        </div>
      )}

      {pages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-4 text-sm">
          {page > 1 && (
            <Link href={`/skillsets?page=${page - 1}`} className={pageLink}>
              <ChevronLeft className="h-4 w-4" />
              Prev
            </Link>
          )}
          <span className="text-muted-foreground">
            {page} / {pages}
          </span>
          {page < pages && (
            <Link href={`/skillsets?page=${page + 1}`} className={pageLink}>
              Next
              <ChevronRight className="h-4 w-4" />
            </Link>
          )}
        </div>
      )}
    </div>
  );
}
