import { cn } from "@/lib/utils";
import { Star } from "lucide-react";

interface StarRatingProps {
  value: number;
  count?: number;
  readonly?: boolean;
  className?: string;
}

export function StarRating({ value, count, readonly = false, className }: StarRatingProps) {
  const stars = Array.from({ length: 5 }, (_, i) => i + 1);

  return (
    <span className={cn("inline-flex items-center gap-1", className)}>
      <span className="flex items-center">
        {stars.map((star) => (
          <Star
            key={star}
            className={cn(
              "h-3.5 w-3.5",
              star <= Math.round(value)
                ? "fill-yellow-400 text-yellow-400"
                : "fill-muted text-muted-foreground",
              !readonly && "cursor-not-allowed opacity-50",
            )}
          />
        ))}
      </span>
      {count !== undefined && count > 0 && (
        <span className="text-xs text-muted-foreground">
          {value.toFixed(1)} ({count})
        </span>
      )}
      {count === 0 && <span className="text-xs text-muted-foreground">No ratings</span>}
    </span>
  );
}
