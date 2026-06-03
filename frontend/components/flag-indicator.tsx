import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

interface FlagIndicatorProps {
  count: number;
  isMine?: boolean;
  className?: string;
}

export function FlagIndicator({ count, isMine, className }: FlagIndicatorProps) {
  if (count === 0 && !isMine) return null;
  if (isMine) {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1 rounded-full bg-orange-100 text-orange-800 px-2 py-0.5 text-xs font-medium",
          className,
        )}
        title="Flagged by you"
      >
        <AlertTriangle className="h-3 w-3" />
        Flagged by you
      </span>
    );
  }
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full bg-yellow-100 text-yellow-800 px-2 py-0.5 text-xs font-medium",
        className,
      )}
      title={`${count} unresolved flag${count > 1 ? "s" : ""}`}
    >
      <AlertTriangle className="h-3 w-3" />
      {count}
    </span>
  );
}
