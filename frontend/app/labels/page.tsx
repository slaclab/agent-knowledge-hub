import { listLabels } from "@/lib/api";
import Link from "next/link";
import { Tag } from "lucide-react";

export const metadata = { title: "Labels — Agent Knowledge Hub" };

export default async function LabelsPage() {
  const labels = await listLabels({ server: true, limit: 500 });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Labels</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Community tags applied to skills. Click a label to browse matching skills.
        </p>
      </div>

      {labels.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <Tag className="h-8 w-8 mx-auto mb-3 opacity-40" />
          <p>No labels yet. Labels are added by community members on skill pages.</p>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {labels.map((label) => (
            <Link
              key={label.name}
              href={`/skills?labels=${encodeURIComponent(label.name)}`}
              className="inline-flex items-center gap-1.5 rounded-full border bg-secondary text-secondary-foreground px-3 py-1 text-sm font-medium hover:bg-secondary/70 transition-colors"
            >
              {label.name}
              <span className="text-xs text-muted-foreground tabular-nums">{label.usage_count}</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
