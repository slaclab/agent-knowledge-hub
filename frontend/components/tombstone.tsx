import Link from "next/link";
import { AlertTriangle } from "lucide-react";

interface TombstoneProps {
  reason: string | null;
  superseded_by_slug?: string | null;
}

export function Tombstone({ reason, superseded_by_slug }: TombstoneProps) {
  return (
    <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-6 space-y-2">
      <div className="flex items-center gap-2 text-destructive">
        <AlertTriangle className="h-5 w-5" />
        <h2 className="font-semibold">This skill has been deactivated</h2>
      </div>
      {reason && <p className="text-sm text-muted-foreground">{reason}</p>}
      {superseded_by_slug && (
        <p className="text-sm">
          Replaced by:{" "}
          <Link href={`/skills/${superseded_by_slug}`} className="text-primary underline">
            {superseded_by_slug}
          </Link>
        </p>
      )}
    </div>
  );
}
